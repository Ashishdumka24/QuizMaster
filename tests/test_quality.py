"""TQM centre pages, CRUD and chart generation."""
import pytest

from backend.extensions import db
from backend.models import Defect, FMEAItem, PDCAAction

PAGES = ["/admin/quality/", "/admin/quality/defects", "/admin/quality/defects?severity=High&status=Open",
         "/admin/quality/defects/new", "/admin/quality/pareto", "/admin/quality/fishbone",
         "/admin/quality/control-chart", "/admin/quality/fmea", "/admin/quality/fmea/new", "/admin/quality/pdca",
         "/admin/quality/pdca/new", "/admin/quality/sipoc", "/admin/quality/changelog", "/admin/quality/report"]


@pytest.mark.parametrize("url", PAGES)
def test_quality_pages(admin_client, url):
    r = admin_client.get(url)
    assert r.status_code == 200, url


@pytest.mark.parametrize("name", ["pareto", "fishbone", "control", "histogram", "fmea"])
def test_chart_pngs(admin_client, name):
    r = admin_client.get(f"/admin/quality/charts/{name}.png")
    assert r.status_code == 200 and r.mimetype == "image/png" and r.data[:4] == b"\x89PNG"


def test_edit_pages(admin_client, app):
    with app.app_context():
        d, f, p = Defect.query.first().id, FMEAItem.query.first().id, PDCAAction.query.first().id
    for url in (f"/admin/quality/defects/{d}", f"/admin/quality/fmea/{f}", f"/admin/quality/pdca/{p}",
                f"/admin/quality/pdca/new?defect={d}"):
        assert admin_client.get(url).status_code == 200, url


def test_fmea_rpn_and_validation(admin_client, app):
    r = admin_client.post("/admin/quality/fmea/new", data={
        "process_step": "Submit", "failure_mode": "Timeout", "effect": "Lost result", "cause": "Slow DB",
        "severity": "8", "occurrence": "3", "detection": "4"})
    assert r.status_code == 302
    with app.app_context():
        item = FMEAItem.query.filter_by(failure_mode="Timeout").one()
        assert item.rpn == 96 and item.risk_level == "Medium"
    r = admin_client.post("/admin/quality/fmea/new", data={
        "process_step": "Submit", "failure_mode": "Bad", "effect": "x", "cause": "y",
        "severity": "11", "occurrence": "0", "detection": "abc"})
    assert r.status_code == 200  # out-of-bounds ratings rejected (input bounds test)


def test_defect_requires_corrective_action_to_resolve(admin_client, app):
    data = {"title": "Timer drift on slow devices", "defect_type": "Timer / Submission",
            "fishbone_category": "Software Code", "severity": "High", "status": "Resolved", "source": "testing",
            "occurrences": "2"}
    assert admin_client.post("/admin/quality/defects/new", data=data).status_code == 200
    data["corrective_action"] = "Timer derived from server deadline"
    assert admin_client.post("/admin/quality/defects/new", data=data).status_code == 302
    with app.app_context():
        d = Defect.query.filter_by(title="Timer drift on slow devices").one()
        assert d.code.startswith("DEF-") and d.resolved_at is not None


def test_pdca_stage_gate(admin_client):
    r = admin_client.post("/admin/quality/pdca/new", data={"title": "Speed up grading", "stage": "Check"})
    assert r.status_code == 200  # cannot jump to Check without Plan and Do notes
    r = admin_client.post("/admin/quality/pdca/new", data={"title": "Speed up grading", "stage": "Check",
                                                          "plan": "p", "do": "d"})
    assert r.status_code == 302


def test_exports(admin_client):
    for url in ("/admin/quality/defects/export?format=xlsx", "/admin/quality/fmea/export?format=pdf",
                "/admin/quality/fmea/export?format=csv"):
        r = admin_client.get(url)
        assert r.status_code == 200 and r.data, url


def test_no_missing_icons_after_rendering(admin_client, student_client):
    from backend.icons import MISSING_ICONS
    for url in PAGES:
        admin_client.get(url)
    for url in ("/student/dashboard", "/explore", "/student/history", "/account/profile", "/account/settings"):
        student_client.get(url)
    assert not MISSING_ICONS, sorted(MISSING_ICONS)
