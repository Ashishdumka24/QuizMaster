"""Quality Center – the TQM toolkit implemented on live data (admin only).

Defect log & check sheet, Pareto (80/20), Ishikawa fishbone, FMEA with RPN,
PDCA action tracker, SIPOC & CTQ tree, I-MR control chart, CTQ metrics,
version log, and a printable consolidated TQM report.
"""
from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from ..extensions import db
from ..models import (DEFECT_SOURCES, DEFECT_STATUSES, DEFECT_TYPES, FISHBONE_CATEGORIES, PDCA_STAGES, SEVERITIES,
                      ChangelogEntry, Defect, FMEAItem, PDCAAction, QuizAttempt)
from ..security import admin_required
from ..services import charts
from ..services.core import log_action, notify
from ..services.exports import export
from ..services.quality import (checksheet, control_chart, ctq_metrics, defect_summary, fishbone_data, fmea_summary,
                                grading_reproducibility, pareto_data, pdca_summary)
from ..utils import clean_text, fmt_dt, paginate, to_int, utcnow

bp = Blueprint("quality", __name__)


@bp.before_request
@admin_required
def _guard():
    return None


@bp.route("/")
def overview():
    return render_template("tqm/overview.html", ctq=ctq_metrics(), defects=defect_summary(), fmea=fmea_summary(),
                           pdca=pdca_summary(), pareto=pareto_data(), repro=grading_reproducibility(),
                           cc=control_chart())


# ---------------------------------------------------------------------------
# Defect log + check sheet
# ---------------------------------------------------------------------------

def _defect_query():
    q = Defect.query
    s = clean_text(request.args.get("q"), 100)
    if s:
        q = q.filter(or_(Defect.title.ilike(f"%{s}%"), Defect.code.ilike(f"%{s}%"), Defect.module.ilike(f"%{s}%")))
    for field, values in (("status", DEFECT_STATUSES), ("severity", SEVERITIES), ("defect_type", DEFECT_TYPES),
                          ("source", tuple(DEFECT_SOURCES))):
        v = request.args.get(field)
        if v in values:
            q = q.filter(getattr(Defect, field) == v)
    return q.order_by(Defect.detected_at.desc())


@bp.route("/defects")
def defects():
    return render_template("tqm/defects.html", page=paginate(_defect_query(), per_page=15), sheet=checksheet(),
                           args=request.args, statuses=DEFECT_STATUSES, severities=SEVERITIES, types=DEFECT_TYPES,
                           sources=DEFECT_SOURCES, summary=defect_summary())


@bp.route("/defects/export")
def defects_export():
    rows = [[d.code, d.title, d.module or "", d.defect_type, d.fishbone_category, d.severity, d.status, d.source,
             d.occurrences, d.root_cause or "", d.corrective_action or "", d.preventive_action or "",
             fmt_dt(d.detected_at), fmt_dt(d.resolved_at)] for d in _defect_query().all()]
    return export(request.args.get("format", "csv"), "quizmaster-defect-register", "Defect Register",
                  ["ID", "Title", "Module", "Type", "Fishbone", "Severity", "Status", "Source", "Occurrences",
                   "Root cause", "Corrective action", "Preventive action", "Detected", "Resolved"], rows)


def _defect_form(defect: Defect, is_new: bool):
    errors = {}
    if request.method == "POST":
        f = request.form
        title = clean_text(f.get("title"), 160)
        if len(title) < 5:
            errors["title"] = "Title must be at least 5 characters."
        occ = to_int(f.get("occurrences"), None, 1, 10000)
        if occ is None:
            errors["occurrences"] = "Occurrences must be a whole number ≥ 1."
        for field, allowed in (("defect_type", DEFECT_TYPES), ("fishbone_category", FISHBONE_CATEGORIES),
                               ("severity", SEVERITIES), ("status", DEFECT_STATUSES),
                               ("source", tuple(DEFECT_SOURCES))):
            if f.get(field) not in allowed:
                errors[field] = "Choose a value from the list."
        if f.get("status") in ("Resolved", "Verified", "Closed") and not clean_text(f.get("corrective_action")):
            errors["corrective_action"] = "Record the corrective action before resolving the defect."
        if not errors:
            old_status = defect.status
            defect.title = title
            for field in ("description", "module", "root_cause", "corrective_action", "preventive_action",
                          "steps_to_reproduce"):
                setattr(defect, field, clean_text(f.get(field), 3000) or None)
            for field in ("defect_type", "fishbone_category", "severity", "status", "source"):
                setattr(defect, field, f.get(field))
            defect.occurrences = occ
            if defect.status in ("Resolved", "Verified", "Closed") and not defect.resolved_at:
                defect.resolved_at = utcnow()
            if defect.status in ("Open", "In Progress"):
                defect.resolved_at = None
            if defect.status == "Verified" and not defect.verified_at:
                defect.verified_at = utcnow()
            if is_new:
                defect.reported_by = current_user.id
                db.session.add(defect)
            db.session.flush()
            if not defect.code:
                defect.code = f"DEF-{defect.id:03d}"
            if not is_new and old_status != defect.status and defect.reported_by and \
                    defect.source == "user_report" and defect.reported_by != current_user.id:
                notify(defect.reported_by, f"Bug {defect.code} is now {defect.status}", defect.title, None, "info")
            log_action("defect_created" if is_new else "defect_updated", "defect", defect.id,
                       f"{defect.code} status={defect.status}")
            db.session.commit()
            flash(f"Defect {defect.code} saved.", "success")
            return redirect(url_for("quality.defects"))
    return render_template("tqm/defect_form.html", d=defect, is_new=is_new, errors=errors, form=request.form,
                           statuses=DEFECT_STATUSES, severities=SEVERITIES, types=DEFECT_TYPES,
                           fishbone=FISHBONE_CATEGORIES, sources=DEFECT_SOURCES)


@bp.route("/defects/new", methods=["GET", "POST"])
def defect_new():
    return _defect_form(Defect(status="Open", severity="Medium", occurrences=1, source="testing",
                               fishbone_category="Software Code", defect_type="Other"), True)


@bp.route("/defects/<int:defect_id>", methods=["GET", "POST"])
def defect_edit(defect_id):
    return _defect_form(db.session.get(Defect, defect_id) or abort(404), False)


@bp.route("/defects/<int:defect_id>/delete", methods=["POST"])
def defect_delete(defect_id):
    d = db.session.get(Defect, defect_id) or abort(404)
    log_action("defect_deleted", "defect", d.id, d.code)
    PDCAAction.query.filter_by(defect_id=d.id).update({PDCAAction.defect_id: None})
    db.session.delete(d)
    db.session.commit()
    flash("Defect deleted.", "success")
    return redirect(url_for("quality.defects"))


# ---------------------------------------------------------------------------
# Pareto / Fishbone / Control chart pages + Matplotlib PNG endpoints
# ---------------------------------------------------------------------------

@bp.route("/pareto")
def pareto():
    return render_template("tqm/pareto.html", data=pareto_data())


@bp.route("/fishbone")
def fishbone():
    return render_template("tqm/fishbone.html", data=fishbone_data())


@bp.route("/control-chart")
def control():
    scores = [a.percentage or 0 for a in QuizAttempt.query.filter(
        QuizAttempt.status.in_(("submitted", "expired"))).all()]
    return render_template("tqm/control.html", cc=control_chart(), ctq=ctq_metrics(), n_scores=len(scores))


@bp.route("/charts/<name>.png")
def chart_png(name):
    if name == "pareto":
        png = charts.pareto_png(pareto_data())
    elif name == "fishbone":
        png = charts.fishbone_png(fishbone_data())
    elif name == "control":
        png = charts.control_chart_png(control_chart())
    elif name == "histogram":
        png = charts.histogram_png([a.percentage or 0 for a in QuizAttempt.query.filter(
            QuizAttempt.status.in_(("submitted", "expired"))).all()])
    elif name == "fmea":
        png = charts.fmea_png(FMEAItem.query.all())
    else:
        abort(404)
    resp = Response(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store"
    if request.args.get("download"):
        resp.headers["Content-Disposition"] = f"attachment; filename=quizmaster-{name}.png"
    return resp


# ---------------------------------------------------------------------------
# FMEA
# ---------------------------------------------------------------------------

@bp.route("/fmea")
def fmea():
    items = sorted(FMEAItem.query.all(), key=lambda i: -i.rpn)
    return render_template("tqm/fmea.html", items=items, summary=fmea_summary())


@bp.route("/fmea/export")
def fmea_export():
    items = sorted(FMEAItem.query.all(), key=lambda i: -i.rpn)
    rows = [[i.id, i.process_step, i.failure_mode, i.effect, i.cause, i.current_controls or "", i.severity,
             i.occurrence, i.detection, i.rpn, i.recommended_action or "", i.owner or "", i.action_status,
             i.new_rpn or ""] for i in items]
    return export(request.args.get("format", "csv"), "quizmaster-fmea", "FMEA Matrix",
                  ["#", "Process step", "Failure mode", "Effect", "Cause", "Controls", "S", "O", "D", "RPN",
                   "Recommended action", "Owner", "Status", "New RPN"], rows,
                  **({"widths": [6, 22, 34, 34, 30, 26, 5, 5, 5, 8, 36, 14, 16, 10]}
                     if request.args.get("format") == "pdf" else {}))


def _fmea_form(item: FMEAItem, is_new: bool):
    errors = {}
    if request.method == "POST":
        f = request.form
        for field in ("process_step", "failure_mode", "effect", "cause"):
            if len(clean_text(f.get(field))) < 3:
                errors[field] = "Required (3+ characters)."
        for field in ("severity", "occurrence", "detection"):
            if to_int(f.get(field), None, 1, 10) is None:
                errors[field] = "Rate 1–10."
        for field in ("new_severity", "new_occurrence", "new_detection"):
            if f.get(field) and to_int(f.get(field), None, 1, 10) is None:
                errors[field] = "Rate 1–10 or leave blank."
        if not errors:
            item.process_step = clean_text(f.get("process_step"), 100)
            item.failure_mode = clean_text(f.get("failure_mode"), 200)
            item.effect = clean_text(f.get("effect"), 300)
            item.cause = clean_text(f.get("cause"), 300)
            item.current_controls = clean_text(f.get("current_controls"), 300) or None
            item.recommended_action = clean_text(f.get("recommended_action"), 400) or None
            item.owner = clean_text(f.get("owner"), 80) or None
            item.action_status = f.get("action_status") if f.get("action_status") in (
                "Planned", "Implemented", "Verified") else "Planned"
            for field in ("severity", "occurrence", "detection"):
                setattr(item, field, to_int(f.get(field)))
            for field in ("new_severity", "new_occurrence", "new_detection"):
                setattr(item, field, to_int(f.get(field)) if f.get(field) else None)
            if is_new:
                db.session.add(item)
            db.session.flush()
            log_action("fmea_created" if is_new else "fmea_updated", "fmea", item.id, f"RPN={item.rpn}")
            db.session.commit()
            flash(f"FMEA entry saved (RPN {item.rpn}).", "success")
            return redirect(url_for("quality.fmea"))
    return render_template("tqm/fmea_form.html", item=item, is_new=is_new, errors=errors, form=request.form)


@bp.route("/fmea/new", methods=["GET", "POST"])
def fmea_new():
    return _fmea_form(FMEAItem(severity=5, occurrence=5, detection=5), True)


@bp.route("/fmea/<int:item_id>", methods=["GET", "POST"])
def fmea_edit(item_id):
    return _fmea_form(db.session.get(FMEAItem, item_id) or abort(404), False)


@bp.route("/fmea/<int:item_id>/delete", methods=["POST"])
def fmea_delete(item_id):
    item = db.session.get(FMEAItem, item_id) or abort(404)
    log_action("fmea_deleted", "fmea", item.id, item.failure_mode[:80])
    db.session.delete(item)
    db.session.commit()
    flash("FMEA entry deleted.", "success")
    return redirect(url_for("quality.fmea"))


# ---------------------------------------------------------------------------
# PDCA action tracker
# ---------------------------------------------------------------------------

@bp.route("/pdca")
def pdca():
    items = PDCAAction.query.order_by(PDCAAction.updated_at.desc()).all()
    board = {s: [i for i in items if i.stage == s] for s in PDCA_STAGES}
    return render_template("tqm/pdca.html", board=board, stages=PDCA_STAGES, items=items)


def _pdca_form(item: PDCAAction, is_new: bool):
    errors = {}
    if request.method == "POST":
        f = request.form
        title = clean_text(f.get("title"), 160)
        if len(title) < 5:
            errors["title"] = "Title must be at least 5 characters."
        stage = f.get("stage") if f.get("stage") in PDCA_STAGES else "Plan"
        order = {s: i for i, s in enumerate(PDCA_STAGES)}
        required = {"Do": "plan", "Check": "do", "Act": "check", "Closed": "act"}
        for st, fld in required.items():
            if order[stage] >= order[st] and not clean_text(f.get(fld)):
                errors[fld] = f"Complete the {fld.title()} section before moving to {st}."
        due = None
        if f.get("due_date"):
            try:
                due = datetime.strptime(f.get("due_date"), "%Y-%m-%d").date()
            except ValueError:
                errors["due_date"] = "Invalid date."
        if not errors:
            item.title, item.stage, item.due_date = title, stage, due
            for field in ("objective", "plan", "do", "check", "act", "metric_name", "baseline_value", "target_value",
                          "result_value", "owner"):
                setattr(item, field, clean_text(f.get(field), 3000) or None)
            did = to_int(f.get("defect_id"))
            item.defect_id = did if did and db.session.get(Defect, did) else None
            if is_new:
                db.session.add(item)
            db.session.flush()
            log_action("pdca_created" if is_new else "pdca_updated", "pdca", item.id, f"stage={stage}")
            db.session.commit()
            flash("PDCA action saved.", "success")
            return redirect(url_for("quality.pdca"))
    return render_template("tqm/pdca_form.html", item=item, is_new=is_new, errors=errors, form=request.form,
                           stages=PDCA_STAGES, defects=Defect.query.order_by(Defect.id.desc()).all())


@bp.route("/pdca/new", methods=["GET", "POST"])
def pdca_new():
    return _pdca_form(PDCAAction(stage="Plan", defect_id=to_int(request.args.get("defect"))), True)


@bp.route("/pdca/<int:item_id>", methods=["GET", "POST"])
def pdca_edit(item_id):
    return _pdca_form(db.session.get(PDCAAction, item_id) or abort(404), False)


@bp.route("/pdca/<int:item_id>/delete", methods=["POST"])
def pdca_delete(item_id):
    item = db.session.get(PDCAAction, item_id) or abort(404)
    log_action("pdca_deleted", "pdca", item.id, item.title)
    db.session.delete(item)
    db.session.commit()
    flash("PDCA action deleted.", "success")
    return redirect(url_for("quality.pdca"))


# ---------------------------------------------------------------------------
# SIPOC / CTQ, version log, consolidated report
# ---------------------------------------------------------------------------

@bp.route("/sipoc")
def sipoc():
    from ..quality_goals import QUALITY_GOALS
    return render_template("tqm/sipoc.html", ctq=ctq_metrics(), goals=QUALITY_GOALS)


@bp.route("/changelog", methods=["GET", "POST"])
def changelog():
    errors = {}
    if request.method == "POST":
        f = request.form
        version = clean_text(f.get("version"), 20)
        title = clean_text(f.get("title"), 160)
        changes = clean_text(f.get("changes"), 4000)
        ctype = f.get("change_type") if f.get("change_type") in ("feature", "fix", "improvement",
                                                                  "security") else "feature"
        try:
            released = datetime.strptime(f.get("released_on", ""), "%Y-%m-%d").date()
        except ValueError:
            released = None
            errors["released_on"] = "Choose a release date."
        if not version:
            errors["version"] = "Version is required (e.g. 1.1.0)."
        if len(title) < 3:
            errors["title"] = "Title is required."
        if len(changes) < 3:
            errors["changes"] = "List at least one change."
        if not errors:
            e = ChangelogEntry(version=version, title=title, changes=changes, change_type=ctype, released_on=released)
            db.session.add(e)
            db.session.flush()
            log_action("changelog_added", "changelog", e.id, version)
            db.session.commit()
            flash(f"Version {version} added to the version log.", "success")
            return redirect(url_for("quality.changelog"))
    entries = ChangelogEntry.query.order_by(ChangelogEntry.released_on.desc(), ChangelogEntry.id.desc()).all()
    return render_template("tqm/changelog.html", entries=entries, errors=errors, form=request.form,
                           today=date.today().isoformat())


@bp.route("/changelog/<int:entry_id>/delete", methods=["POST"])
def changelog_delete(entry_id):
    e = db.session.get(ChangelogEntry, entry_id) or abort(404)
    log_action("changelog_deleted", "changelog", e.id, e.version)
    db.session.delete(e)
    db.session.commit()
    flash("Version log entry deleted.", "success")
    return redirect(url_for("quality.changelog"))


@bp.route("/report")
def report():
    return render_template("tqm/report.html", ctq=ctq_metrics(), defects=defect_summary(), sheet=checksheet(),
                           pareto=pareto_data(), fishbone=fishbone_data(),
                           fmea=sorted(FMEAItem.query.all(), key=lambda i: -i.rpn), fmea_sum=fmea_summary(),
                           pdca=PDCAAction.query.order_by(PDCAAction.created_at).all(), cc=control_chart(),
                           repro=grading_reproducibility(), generated=utcnow(),
                           defect_rows=Defect.query.order_by(Defect.id).all())
