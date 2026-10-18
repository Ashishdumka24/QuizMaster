"""Shared pytest fixtures. Every test gets a fresh in-memory SQLite database
seeded with the demo content, one verified student and one verified admin.
The passwords below exist only inside the test process."""
import os
import re

os.environ.setdefault("APP_ENV", "testing")

import pytest  # noqa: E402

from config import TestingConfig  # noqa: E402
from quizmaster import create_app  # noqa: E402
from quizmaster.extensions import db  # noqa: E402
from quizmaster.models import User  # noqa: E402
from quizmaster.seed import seed_all  # noqa: E402
from quizmaster.utils import utcnow  # noqa: E402

STUDENT_PW = "Student#Pass2026"
ADMIN_PW = "Admin#Pass2026x"


import jinja2  # noqa: E402
from jinja2.utils import missing  # noqa: E402


class _NameStrictUndefined(jinja2.Undefined):
    """Fails on undefined *variables* (missing view context) while still allowing
    the ``errors.field`` / ``dict.key`` lookups templates use for optional keys."""

    def _strict(self):
        if self._undefined_obj is missing:
            self._fail_with_undefined_error()

    def __str__(self):
        self._strict()
        return ""

    def __bool__(self):
        self._strict()
        return False

    def __iter__(self):
        self._strict()
        return iter(())


class _Cfg(TestingConfig):
    pass


@pytest.fixture()
def app(tmp_path):
    class Cfg(_Cfg):
        INSTANCE_DIR = tmp_path
    application = create_app(Cfg)
    if os.environ.get("QM_STRICT_TEMPLATES"):
        application.jinja_env.undefined = _NameStrictUndefined
    with application.app_context():
        db.create_all()
        seed_all()
        for email, name, role, pw in (("student@example.test", "Asha Kumar", "student", STUDENT_PW),
                                      ("admin@example.test", "Ravi Admin", "admin", ADMIN_PW)):
            u = User(full_name=name, email=email, role=role, email_verified_at=utcnow())
            u.set_password(pw)
            db.session.add(u)
        db.session.commit()
    # Requests must run outside a long-lived app context: otherwise ``g`` (and
    # Flask-Login's cached user) would leak between independent test clients.
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password, portal="student"):
    return client.post("/auth/login", data={"email": email, "password": password, "portal": portal},
                       follow_redirects=False)


@pytest.fixture()
def student_client(client):
    r = login(client, "student@example.test", STUDENT_PW)
    assert r.status_code == 302, r.data[:500]
    return client


@pytest.fixture()
def admin_client(client):
    r = login(client, "admin@example.test", ADMIN_PW, portal="admin")
    assert r.status_code == 302, r.data[:500]
    return client


def no_dead_links(html: str) -> bool:
    return not re.search(r'href="#"', html)


def pytest_sessionfinish(session, exitstatus):
    """Report icon names that templates asked for but icons.py does not define."""
    from quizmaster.icons import MISSING_ICONS
    if MISSING_ICONS:
        print("\nMISSING ICONS:", ", ".join(sorted(MISSING_ICONS)))
