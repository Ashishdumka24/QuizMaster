"""Render every GET page for each role and check for server errors and dead links."""
import pytest

from tests.conftest import no_dead_links

PUBLIC = ["/", "/quizzes", "/about", "/help", "/help/manual", "/changelog", "/shortcuts", "/privacy", "/terms",
          "/auth/login", "/auth/login?portal=admin", "/auth/register", "/auth/forgot", "/quizzes?q=python&sort=popular"]
STUDENT = ["/dashboard", "/history", "/results", "/notifications", "/feedback", "/account/profile",
           "/account/security", "/account/settings", "/quizzes", "/leaderboard", "/calendar", "/help"]


@pytest.mark.parametrize("url", PUBLIC)
def test_public_pages(client, url):
    r = client.get(url)
    assert r.status_code == 200, url
    assert no_dead_links(r.get_data(as_text=True))


@pytest.mark.parametrize("url", STUDENT)
def test_student_pages(student_client, url):
    r = student_client.get(url)
    assert r.status_code == 200, (url, r.status_code, r.location)
    assert no_dead_links(r.get_data(as_text=True))


def test_quiz_detail_pages(student_client, app):
    from quizmaster.models import Quiz
    with app.app_context():
        slugs = [q.slug for q in Quiz.query.filter_by(status="published")]
    assert slugs
    for s in slugs:
        r = student_client.get(f"/quizzes/{s}")
        assert r.status_code == 200, s
