"""End-to-end attempt lifecycle through the JSON API the player uses."""
from quizmaster.extensions import db
from quizmaster.models import Quiz, QuizAttempt


def _quiz(app, release="immediate"):
    with app.app_context():
        q = Quiz.query.filter_by(status="published").order_by(Quiz.id).first()
        q.result_release = release
        q.max_attempts = 0
        q.start_at = q.end_at = None
        db.session.commit()
        return q.id, q.slug


def _start(c, slug):
    r = c.post(f"/quizzes/{slug}/start")
    assert r.status_code == 302 and "/attempts/" in r.location
    return int(r.location.rstrip("/").split("/")[-1])


def test_full_attempt_cycle(student_client, app):
    qid, slug = _quiz(app)
    c = student_client
    aid = _start(c, slug)
    assert c.get(f"/attempts/{aid}").status_code == 200
    state = c.get(f"/api/attempts/{aid}/state").get_json()
    assert state["ok"]
    data = state["data"]
    assert data["questions"] and data["remaining"] > 0
    # answer key must never be sent to the browser
    for q in data["questions"]:
        assert "correct" not in q and "accepted" not in q and "explanation" not in q
    first = data["questions"][0]
    resp = {"options": [first["options"][0]["id"]]} if first.get("options") else {"text": "x"}
    r = c.post(f"/api/attempts/{aid}/answers", json={"answers": [{"question_id": first["id"], "response": resp,
                                                                   "marked": True}]})
    assert r.get_json()["ok"], r.get_json()
    r1 = c.post(f"/api/attempts/{aid}/submit", json={})
    assert r1.get_json()["ok"]
    r2 = c.post(f"/api/attempts/{aid}/submit", json={})  # idempotent
    assert r2.get_json()["ok"] and r2.get_json()["data"]["duplicate"]
    r3 = c.post(f"/api/attempts/{aid}/answers", json={"answers": []})
    assert r3.status_code == 409 and "result_url" in r3.get_json()["error"] or r3.get_json().get("result_url")
    page = c.get(f"/attempts/{aid}/result")
    assert page.status_code == 200
    with app.app_context():
        a = db.session.get(QuizAttempt, aid)
        assert a.status == "submitted" and a.percentage is not None
        passed = a.passed
    if passed:
        assert c.get(f"/attempts/{aid}/certificate").status_code == 200
    for url in ("/history", "/results", "/dashboard", f"/leaderboard?quiz={qid}", "/leaderboard",
                f"/quizzes/{slug}"):
        assert c.get(url).status_code == 200, url


def test_manual_release_hides_key(student_client, app):
    _, slug = _quiz(app, release="manual")
    c = student_client
    aid = _start(c, slug)
    c.post(f"/api/attempts/{aid}/submit", json={})
    html = c.get(f"/attempts/{aid}/result").get_data(as_text=True)
    assert "result pending" in html
    assert "Answer review" not in html


def test_other_student_cannot_view_attempt(student_client, app):
    _, slug = _quiz(app)
    aid = _start(student_client, slug)
    student_client.post("/auth/logout")
    from quizmaster.models import User
    from quizmaster.utils import utcnow
    with app.app_context():
        u = User(full_name="Other Person", email="other@example.test", role="student", email_verified_at=utcnow())
        u.set_password("Other#Pass2026x")
        db.session.add(u)
        db.session.commit()
    student_client.post("/auth/login", data={"email": "other@example.test", "password": "Other#Pass2026x"})
    assert student_client.get(f"/attempts/{aid}/result").status_code == 404
    assert student_client.get(f"/api/attempts/{aid}/state").status_code == 404


def test_server_deadline_enforced(student_client, app):
    """Answers after deadline + grace are rejected and the attempt is auto-finalised."""
    from datetime import timedelta
    _, slug = _quiz(app)
    aid = _start(student_client, slug)
    with app.app_context():
        a = db.session.get(QuizAttempt, aid)
        a.deadline_at = a.deadline_at - timedelta(hours=5)
        a.started_at = a.started_at - timedelta(hours=5)
        db.session.commit()
    r = student_client.post(f"/api/attempts/{aid}/answers", json={"answers": []})
    assert r.status_code == 409
    with app.app_context():
        a = db.session.get(QuizAttempt, aid)
        assert a.status == "expired" and a.auto_submitted


def test_snapshot_keeps_old_result_when_question_edited(student_client, app):
    from quizmaster.models import Question, QuizQuestion
    qid, slug = _quiz(app)
    aid = _start(student_client, slug)
    student_client.post(f"/api/attempts/{aid}/submit", json={})
    with app.app_context():
        before = db.session.get(QuizAttempt, aid).score
        qq = QuizQuestion.query.filter_by(quiz_id=qid).first()
        q = db.session.get(Question, qq.question_id)
        q.text = "Edited after the attempt"
        q.marks = 50
        db.session.commit()
    html = student_client.get(f"/attempts/{aid}/result").get_data(as_text=True)
    assert "Edited after the attempt" not in html
    with app.app_context():
        assert db.session.get(QuizAttempt, aid).score == before


def test_max_attempts_enforced(student_client, app):
    qid, slug = _quiz(app)
    with app.app_context():
        q = db.session.get(Quiz, qid)
        q.max_attempts = 1
        db.session.commit()
    aid = _start(student_client, slug)
    student_client.post(f"/api/attempts/{aid}/submit", json={})
    r = student_client.post(f"/quizzes/{slug}/start")
    assert r.status_code == 302 and "/attempts/" not in r.location
