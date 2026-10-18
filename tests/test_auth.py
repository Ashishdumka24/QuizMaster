"""Registration, OTP verification, login rules and password reset (dev outbox mode)."""
import json
import re
from datetime import timedelta

from conftest import ADMIN_PW, STUDENT_PW, login
from backend.extensions import db
from backend.models import EmailOTP, PasswordResetToken, User
from backend.utils import utcnow

NEW_PW = "Fresh#Start2026"


def _outbox(app):
    folder = app.config["INSTANCE_DIR"] / "outbox"
    metas = sorted(folder.glob("*.json")) if folder.exists() else []
    return [dict(json.loads(m.read_text()), html=(folder / json.loads(m.read_text())["file"]).read_text()) for m in metas]


def _register(client, email="new.student@example.test", **extra):
    data = {"full_name": "Neha Rao", "email": email, "password": NEW_PW, "confirm_password": NEW_PW,
            "accept_terms": "on", **extra}
    return client.post("/auth/register", data=data)


def _latest_code(app):
    subject = _outbox(app)[-1]["subject"]
    return re.match(r"(\d{6})", subject).group(1)


def test_register_verify_and_login(client, app):
    r = _register(client, role="admin")  # a forged role field must be ignored
    assert r.status_code == 302 and "/auth/verify" in r.location
    with app.app_context():
        u = User.query.filter_by(email="new.student@example.test").one()
        assert u.role == "student" and u.email_verified_at is None
        otp = EmailOTP.query.filter_by(user_id=u.id).one()
        code = _latest_code(app)
        assert code not in otp.code_hash  # stored hashed, never in plain text
    assert client.post("/auth/verify", data={"code": "000000" if code != "000000" else "111111"}).status_code == 200
    r = client.post("/auth/verify", data={"code": code})
    assert r.status_code == 302 and "/dashboard" in r.location
    with app.app_context():
        assert User.query.filter_by(email="new.student@example.test").one().email_verified_at is not None
    # single use: the same code cannot verify again
    with app.app_context():
        assert EmailOTP.query.filter_by(consumed_at=None, invalidated_at=None).count() == 0


def test_duplicate_email_rejected(client):
    r = _register(client, email="student@example.test")
    assert r.status_code == 200 and b"already" in r.data.lower()


def test_weak_password_rejected(client, app):
    r = client.post("/auth/register", data={"full_name": "Weak Pw", "email": "weak@example.test",
                                            "password": "password", "confirm_password": "password",
                                            "accept_terms": "on"})
    assert r.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="weak@example.test").first() is None


def test_otp_attempt_limit(client, app):
    _register(client)
    code = _latest_code(app)
    wrong = "123456" if code != "123456" else "654321"
    for _ in range(app.config["OTP_MAX_ATTEMPTS"]):
        client.post("/auth/verify", data={"code": wrong})
    r = client.post("/auth/verify", data={"code": code})  # even the right code is now locked
    assert r.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="new.student@example.test").one().email_verified_at is None


def test_expired_otp_rejected(client, app):
    _register(client)
    code = _latest_code(app)
    with app.app_context():
        for o in EmailOTP.query.all():
            o.expires_at = utcnow() - timedelta(minutes=1)
        db.session.commit()
    assert client.post("/auth/verify", data={"code": code}).status_code == 200


def test_resend_is_throttled(client, app):
    _register(client)
    before = len(_outbox(app))
    client.post("/auth/verify/resend")
    assert len(_outbox(app)) == before  # cooldown blocks an immediate resend


def test_unverified_login_goes_to_verify(client, app):
    _register(client)
    c2 = app.test_client()
    r = login(c2, "new.student@example.test", NEW_PW)
    assert r.status_code == 302 and "/auth/verify" in r.location


def test_wrong_password_and_disabled_account(client, app):
    r = login(client, "student@example.test", "Wrong#Pass2026")
    assert r.status_code == 200
    with app.app_context():
        u = User.query.filter_by(email="student@example.test").one()
        u.is_active_account = False
        db.session.commit()
    r = login(client, "student@example.test", STUDENT_PW)
    assert r.status_code == 200 and b"disabled" in r.data.lower()


def test_role_based_redirects(app):
    c = app.test_client()
    r = login(c, "admin@example.test", ADMIN_PW, portal="admin")
    assert r.status_code == 302 and "/admin" in r.location
    c = app.test_client()
    r = login(c, "student@example.test", STUDENT_PW, portal="admin")  # student on admin portal → own dashboard
    assert r.status_code == 302 and "/admin" not in r.location


def test_forgot_and_reset_password(client, app):
    r = client.post("/auth/forgot", data={"email": "nobody@example.test"})
    assert r.status_code == 200
    r2 = client.post("/auth/forgot", data={"email": "student@example.test"})
    assert r2.status_code == 200
    # identical response text for known and unknown addresses (no account enumeration)
    assert b"If an active account exists" in r.data and b"If an active account exists" in r2.data
    mails = [m for m in _outbox(app) if m["to"] == "student@example.test"]
    assert len(mails) == 1
    token = re.search(r"/auth/reset/([\w\-]+)", mails[0]["html"]).group(1)
    with app.app_context():
        assert PasswordResetToken.query.one().token_hash != token
    r = client.post(f"/auth/reset/{token}", data={"password": NEW_PW, "confirm_password": NEW_PW})
    assert r.status_code == 302
    # token is single use
    r = client.get(f"/auth/reset/{token}")
    assert r.status_code in (200, 302, 400, 410) and b"Choose a new password" not in r.data
    assert login(app.test_client(), "student@example.test", NEW_PW).status_code == 302
    assert login(app.test_client(), "student@example.test", STUDENT_PW).status_code == 200


def test_logout_requires_post_and_clears_session(student_client):
    assert student_client.get("/auth/logout").status_code == 405
    student_client.post("/auth/logout")
    r = student_client.get("/dashboard")
    assert r.status_code == 302 and "/auth/login" in r.location
