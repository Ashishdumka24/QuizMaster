"""Unit tests for grading rules, input bounds, validation helpers and security controls."""
import pytest

from backend.security import valid_email, validate_password
from backend.services.grading import grade_question, sanitize_response

SINGLE = {"type": "single", "marks": 2, "negative": 0.5, "options": [{"id": 1}, {"id": 2}, {"id": 3}], "correct": [2]}
MULTI = {"type": "multiple", "marks": 3, "negative": 1, "options": [{"id": 1}, {"id": 2}, {"id": 3}], "correct": [1, 3]}
SHORT = {"type": "short", "marks": 1, "negative": 0, "accepted": ["Total Quality Management"]}


def test_single_choice():
    assert grade_question(SINGLE, {"options": [2]}, False) == ("correct", True, 2.0)
    assert grade_question(SINGLE, {"options": [1]}, False) == ("incorrect", False, 0.0)
    assert grade_question(SINGLE, {"options": [1]}, True) == ("incorrect", False, -0.5)
    assert grade_question(SINGLE, None, True) == ("unanswered", None, 0.0)


def test_multiple_is_all_or_nothing():
    assert grade_question(MULTI, {"options": [1, 3]}, False)[0] == "correct"
    assert grade_question(MULTI, {"options": [1]}, False)[0] == "incorrect"
    assert grade_question(MULTI, {"options": [1, 2, 3]}, False)[0] == "incorrect"


def test_text_answers_normalised():
    assert grade_question(SHORT, {"text": "  total   quality management "}, False)[0] == "correct"
    assert grade_question(SHORT, {"text": "TQM!"}, False)[0] == "incorrect"


@pytest.mark.parametrize("raw,expected", [
    ({"options": [99]}, None),              # option not in question → ignored
    ({"options": ["2", "abc", 2]}, {"options": [2]}),
    ({"options": [1, 2]}, {"options": [1]}),  # single choice keeps only one
    ("2", {"options": [2]}),
    (None, None),
])
def test_sanitize_choice(raw, expected):
    assert sanitize_response(SINGLE, raw) == expected


def test_sanitize_text_bounds():
    out = sanitize_response(SHORT, {"text": "x" * 2000 + "\x00"})
    assert len(out["text"]) == 500 and "\x00" not in out["text"]
    assert sanitize_response(SHORT, {"text": "   "}) is None


def test_password_policy():
    assert validate_password("short")
    assert validate_password("alllower")  # 8 chars, one character class
    assert not validate_password("correct horse battery staple")  # long passphrases are allowed
    assert validate_password("Neha#Rao2026", email="neha@example.test")
    assert not validate_password("Quality#Circle2026")


@pytest.mark.parametrize("email,ok", [("a@b.co", True), ("bad", False), ("x@y", False), ("a b@c.com", False)])
def test_email_validation(email, ok):
    assert valid_email(email) is ok


def test_security_headers(client):
    r = client.get("/")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Referrer-Policy" in r.headers


def test_session_cookie_flags(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True


def test_open_redirect_blocked(app):
    from conftest import STUDENT_PW
    c = app.test_client()
    r = c.post("/auth/login?next=https://evil.example/phish",
               data={"email": "student@example.test", "password": STUDENT_PW})
    assert r.status_code == 302 and "evil.example" not in r.location


def test_safe_back_ignores_foreign_referrer(admin_client, app):
    from backend.models import Quiz
    with app.app_context():
        qid = Quiz.query.filter_by(status="published").first().id
    r = admin_client.post(f"/admin/quizzes/{qid}/publish-results", data={"publish": "1"},
                          headers={"Referer": "https://evil.example/x"})
    assert r.status_code == 302 and "evil.example" not in r.location
    r = admin_client.post(f"/admin/quizzes/{qid}/publish-results", data={"publish": "1"},
                          headers={"Referer": "http://localhost/admin/quizzes?status=published"})
    assert r.location.endswith("/admin/quizzes?status=published")


def test_student_cannot_call_admin_api_or_change_role(student_client, app):
    r = student_client.post("/account/profile", data={"full_name": "Asha Kumar", "role": "admin"})
    from backend.models import User
    with app.app_context():
        assert User.query.filter_by(email="student@example.test").one().role == "student"
    assert student_client.get("/admin/").status_code in (302, 403)


def test_csrf_enforced_when_enabled(app):
    app.config["WTF_CSRF_ENABLED"] = True
    c = app.test_client()
    r = c.post("/auth/login", data={"email": "student@example.test", "password": "x"})
    assert r.status_code == 400
    app.config["WTF_CSRF_ENABLED"] = False


def test_upload_rejects_non_image(student_client):
    import io
    r = student_client.post("/account/avatar", data={"avatar": (io.BytesIO(b"<?php echo 1; ?>"), "shell.php.png")},
                            content_type="multipart/form-data")
    assert r.status_code in (302, 400)
    page = student_client.get("/account/profile").data
    assert b"shell.php" not in page


def test_unknown_page_is_friendly_404(client):
    r = client.get("/definitely-not-here")
    assert r.status_code == 404 and b"<html" in r.data
