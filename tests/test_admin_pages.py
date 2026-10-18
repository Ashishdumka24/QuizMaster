"""Render every admin page and exercise core admin workflows."""
import io

import pytest

from backend.extensions import db
from backend.models import Question, Quiz, QuizAttempt, User
from tests.conftest import no_dead_links

ADMIN_PAGES = ["/admin/", "/admin/users", "/admin/users?role=student&status=active&sort=name", "/admin/users/new",
               "/admin/categories", "/admin/quizzes", "/admin/quizzes?status=draft", "/admin/quizzes/new",
               "/admin/questions", "/admin/questions?state=archived", "/admin/questions?type=single&difficulty=easy",
               "/admin/questions/new", "/admin/questions/import", "/admin/results", "/admin/analytics",
               "/admin/analytics?from=2026-01-01&to=2026-12-31", "/admin/announcements", "/admin/inbox",
               "/admin/inbox?tab=feedback", "/admin/audit", "/admin/settings", "/admin/backups",
               "/admin/maintenance", "/admin/errors", "/admin/errors?show=all", "/calendar", "/leaderboard",
               "/account/profile", "/account/security", "/account/settings", "/help"]


@pytest.mark.parametrize("url", ADMIN_PAGES)
def test_admin_pages_render(admin_client, url):
    r = admin_client.get(url)
    assert r.status_code == 200, (url, r.status_code, r.location)
    assert no_dead_links(r.get_data(as_text=True)), url


def test_admin_entity_pages(admin_client, app):
    with app.app_context():
        quiz = Quiz.query.first()
        question = Question.query.first()
        user = User.query.filter_by(role="student").first()
        ids = quiz.id, question.id, user.id
    for url in (f"/admin/quizzes/{ids[0]}/edit", f"/admin/quizzes/{ids[0]}/questions",
                f"/admin/quizzes/{ids[0]}/preview", f"/admin/quizzes/{ids[0]}/analysis",
                f"/admin/questions/{ids[1]}/edit", f"/admin/questions/{ids[1]}/edit?quiz_id={ids[0]}",
                f"/admin/questions/new?quiz_id={ids[0]}", f"/admin/users/{ids[2]}", "/admin/categories?edit=1",
                "/admin/announcements?edit=1"):
        r = admin_client.get(url)
        assert r.status_code == 200, url


def test_student_cannot_access_admin(student_client):
    for url in ("/admin/", "/admin/users", "/admin/quizzes/new", "/admin/quality/"):
        r = student_client.get(url)
        assert r.status_code in (302, 403, 404), url
        if r.status_code == 302:
            assert "/admin" not in r.location


def test_anonymous_redirected_from_admin(client):
    r = client.get("/admin/")
    assert r.status_code == 302 and "/auth/" in r.location


def test_create_quiz_add_question_publish(admin_client, app):
    r = admin_client.post("/admin/quizzes/new", data={"title": "Pytest Quiz", "time_limit_minutes": "5",
                                                      "pass_percentage": "50", "max_attempts": "0",
                                                      "difficulty": "easy", "result_release": "immediate",
                                                      "show_correct_answers": "1"})
    assert r.status_code == 302
    with app.app_context():
        quiz = Quiz.query.filter_by(title="Pytest Quiz").one()
        qid = quiz.id
        assert quiz.status == "draft"
    r = admin_client.post("/admin/questions/new", data={
        "qtype": "single", "text": "Which planet is known as the red planet in our solar system?",
        "option_text": ["Mars", "Venus", "Jupiter", "Saturn"], "option_correct": ["0"], "marks": "2",
        "negative_marks": "0", "difficulty": "easy", "quiz_id": str(qid)})
    assert r.status_code == 302, r.get_data(as_text=True)[:2000]
    r = admin_client.post(f"/admin/quizzes/{qid}/status", data={"status": "published"})
    assert r.status_code == 302
    with app.app_context():
        quiz = db.session.get(Quiz, qid)
        assert quiz.status == "published" and quiz.question_count == 1
    # invalid question (no correct option) is rejected and the form is re-rendered
    r = admin_client.post("/admin/questions/new", data={"qtype": "single", "text": "Broken question without key?",
                                                        "option_text": ["a", "b"], "marks": "1"})
    assert r.status_code == 200


def test_question_import_csv(admin_client, app):
    csv_data = ("type,question,option_a,option_b,option_c,option_d,option_e,option_f,correct,marks,negative_marks,"
                "difficulty,category,topic,tags,explanation\n"
                "single,What is 12 times 12 in base ten?,144,124,112,154,,,A,1,0,easy,,,,\n"
                "truefalse,The Python keyword for a function definition is def.,,,,,,,true,1,0,easy,,,,\n"
                "short,Which gas do plants absorb from the air for photosynthesis?,,,,,,,carbon dioxide|co2,1,0,"
                "medium,,,,\n"
                "single,Row with a bad key letter,x,y,,,,,Z,1,0,easy,,,,\n")
    r = admin_client.post("/admin/questions/import", data={"file": (io.BytesIO(csv_data.encode()), "q.csv")},
                          content_type="multipart/form-data")
    assert r.status_code == 200 and "Nothing was saved" in r.get_data(as_text=True)
    r = admin_client.post("/admin/questions/import", data={"file": (io.BytesIO(csv_data.encode()), "q.csv"),
                                                          "skip_invalid": "1"}, content_type="multipart/form-data")
    assert r.status_code == 200
    with app.app_context():
        assert Question.query.filter(Question.text.like("What is 12 times 12%")).count() == 1


def test_role_change_and_disable(admin_client, app):
    with app.app_context():
        uid = User.query.filter_by(email="student@example.test").one().id
    assert admin_client.post(f"/admin/users/{uid}/action", data={"action": "disable"}).status_code == 302
    with app.app_context():
        assert db.session.get(User, uid).is_active_account is False
    admin_client.post(f"/admin/users/{uid}/action", data={"action": "enable"})
    with app.app_context():
        assert db.session.get(User, uid).is_active_account is True


def test_exports(admin_client):
    for url in ("/admin/users/export?format=csv", "/admin/users/export?format=xlsx", "/admin/results/export?format=pdf",
                "/admin/audit/export?format=csv", "/admin/analytics?format=pdf", "/admin/questions/template.csv"):
        r = admin_client.get(url)
        assert r.status_code == 200, url
        assert r.data, url


def test_question_import_json_and_bad_file(admin_client, app):
    import json as _json
    payload = {"questions": [
        {"type": "multiple", "question": "Which of these are TQM tools used in this project?",
         "options": ["Pareto chart", "Fishbone diagram", "Bubble sort"], "correct": ["a", "b"], "difficulty": "easy"},
        {"type": "fill", "question": "PDCA stands for Plan, Do, Check and ____.", "correct": "Act"},
    ]}
    r = admin_client.post("/admin/questions/import",
                          data={"file": (io.BytesIO(_json.dumps(payload).encode()), "q.json")},
                          content_type="multipart/form-data")
    assert r.status_code == 200
    with app.app_context():
        assert Question.query.filter(Question.text.like("PDCA stands for%")).count() == 1
    r = admin_client.post("/admin/questions/import", data={"file": (io.BytesIO(b"{not json"), "bad.json")},
                          content_type="multipart/form-data")
    assert r.status_code in (200, 400)
    r = admin_client.post("/admin/questions/import", data={"file": (io.BytesIO(b"\xff\xfe\x00"), "x.exe")},
                          content_type="multipart/form-data")
    assert r.status_code in (200, 400)
