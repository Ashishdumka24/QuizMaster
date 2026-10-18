"""Student area: dashboard, history, results analytics, notifications, feedback."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db, limiter
from ..models import (DEFECT_TYPES, Defect, Feedback, Notification, Quiz, QuizAttempt)
from ..security import json_ok, login_required_verified, student_required
from ..services.attempts import finalize_overdue, result_released
from ..services.core import log_action, notify_role
from ..services.stats import announcements_for, recommendations, student_stats
from ..utils import clean_text, paginate, to_int, utcnow

bp = Blueprint("student", __name__)


@bp.route("/dashboard")
@student_required
def dashboard():
    finalize_overdue(user_id=current_user.id)
    stats = student_stats(current_user)
    recent = (QuizAttempt.query.filter_by(user_id=current_user.id)
              .order_by(QuizAttempt.started_at.desc()).limit(5).all())
    in_progress = [a for a in recent if a.status == "in_progress"]
    return render_template("student/dashboard.html", stats=stats, recent=recent, in_progress=in_progress,
                           recommended=recommendations(current_user), announcements=announcements_for(current_user),
                           released=result_released)


@bp.route("/history")
@student_required
def history():
    finalize_overdue(user_id=current_user.id)
    q = QuizAttempt.query.filter(QuizAttempt.user_id == current_user.id).join(Quiz)
    search = clean_text(request.args.get("q"), 100)
    status = request.args.get("status", "")
    if search:
        q = q.filter(Quiz.title.ilike(f"%{search}%"))
    if status in ("in_progress", "submitted", "expired"):
        q = q.filter(QuizAttempt.status == status)
    elif status == "passed":
        q = q.filter(QuizAttempt.passed.is_(True))
    elif status == "failed":
        q = q.filter(QuizAttempt.passed.is_(False))
    sort = request.args.get("sort", "newest")
    order = {"newest": QuizAttempt.started_at.desc(), "oldest": QuizAttempt.started_at.asc(),
             "score": QuizAttempt.percentage.desc().nullslast()}.get(sort, QuizAttempt.started_at.desc())
    page = paginate(q.order_by(order), per_page=10)
    return render_template("student/history.html", page=page, search=search, status=status, sort=sort,
                           released=result_released)


@bp.route("/results")
@student_required
def results():
    finalize_overdue(user_id=current_user.id)
    stats = student_stats(current_user)
    attempts = (QuizAttempt.query.filter(QuizAttempt.user_id == current_user.id,
                                         QuizAttempt.status.in_(("submitted", "expired")))
                .order_by(QuizAttempt.submitted_at.desc()).all())
    released = [a for a in attempts if result_released(a)]
    pending = [a for a in attempts if not result_released(a)]
    return render_template("student/results.html", stats=stats, released=released[:30], pending=pending)


# ---------------------------------------------------------------------------
# Notifications (shared by all roles)
# ---------------------------------------------------------------------------

@bp.route("/notifications")
@login_required_verified
def notifications():
    q = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc())
    page = paginate(q, per_page=15)
    return render_template("student/notifications.html", page=page)


@bp.route("/api/notifications")
@login_required_verified
def api_notifications():
    items = (Notification.query.filter_by(user_id=current_user.id)
             .order_by(Notification.created_at.desc()).limit(8).all())
    unread = Notification.query.filter_by(user_id=current_user.id, read_at=None).count()
    from ..utils import time_ago
    return json_ok({"unread": unread, "items": [
        {"id": n.id, "title": n.title, "body": n.body, "link": n.link, "kind": n.kind,
         "read": n.read_at is not None, "ago": time_ago(n.created_at)} for n in items]})


@bp.route("/api/notifications/read", methods=["POST"])
@login_required_verified
def api_notifications_read():
    payload = request.get_json(silent=True) or {}
    q = Notification.query.filter_by(user_id=current_user.id, read_at=None)
    nid = to_int(payload.get("id") or request.form.get("id"))
    if nid:
        q = q.filter_by(id=nid)
    count = q.update({Notification.read_at: utcnow()}, synchronize_session=False)
    db.session.commit()
    if request.is_json:
        return json_ok({"marked": count})
    flash("Notifications marked as read.", "success")
    return redirect(request.referrer or url_for("student.notifications"))


@bp.route("/notifications/clear", methods=["POST"])
@login_required_verified
def notifications_clear():
    Notification.query.filter(Notification.user_id == current_user.id, Notification.read_at.isnot(None)).delete()
    db.session.commit()
    flash("Read notifications cleared.", "success")
    return redirect(url_for("student.notifications"))


# ---------------------------------------------------------------------------
# Feedback & bug reports (TQM customer focus + PDCA input; Q08 / Q19)
# ---------------------------------------------------------------------------

FEEDBACK_AREAS = {"general": "General experience", "quiz": "Taking quizzes", "results": "Results & analytics",
                  "design": "Design & usability", "performance": "Speed & performance",
                  "accessibility": "Accessibility"}


@bp.route("/feedback", methods=["GET", "POST"])
@login_required_verified
@limiter.limit("10 per hour", methods=["POST"])
def feedback():
    errors = {}
    if request.method == "POST":
        kind = request.form.get("kind")
        if kind == "feedback":
            rating = to_int(request.form.get("rating"), None, 1, 5)
            area = request.form.get("area") if request.form.get("area") in FEEDBACK_AREAS else "general"
            message = clean_text(request.form.get("message"), 2000)
            if rating is None:
                errors["rating"] = "Choose a rating from 1 to 5 stars."
            if not errors:
                fb = Feedback(user_id=current_user.id, rating=rating, area=area, message=message or None)
                db.session.add(fb)
                db.session.flush()
                log_action("feedback_submitted", "feedback", fb.id, f"rating={rating}; area={area}")
                db.session.commit()
                flash("Thank you! Your feedback helps us improve QuizMaster.", "success")
                return redirect(url_for("student.feedback"))
        elif kind == "bug":
            title = clean_text(request.form.get("title"), 160)
            description = clean_text(request.form.get("description"), 3000)
            steps = clean_text(request.form.get("steps"), 2000)
            dtype = request.form.get("defect_type") if request.form.get("defect_type") in DEFECT_TYPES else "Other"
            severity = request.form.get("severity") if request.form.get("severity") in ("Low", "Medium", "High",
                                                                                          "Critical") else "Medium"
            if len(title) < 5:
                errors["title"] = "Give the problem a short title (5+ characters)."
            if len(description) < 10:
                errors["description"] = "Describe what happened (10+ characters)."
            if not errors:
                d = Defect(title=title, description=description, steps_to_reproduce=steps or None,
                           defect_type=dtype, severity=severity, source="user_report", status="Open",
                           fishbone_category="Software Code", module="Reported by user",
                           reported_by=current_user.id, reporter_email=current_user.email)
                db.session.add(d)
                db.session.flush()
                d.code = f"DEF-{d.id:03d}"
                notify_role("admin", f"New bug report {d.code}", title, url_for("quality.defect_edit", defect_id=d.id),
                            "warning")
                log_action("bug_reported", "defect", d.id, title)
                db.session.commit()
                flash(f"Bug report {d.code} submitted. Our team will investigate it.", "success")
                return redirect(url_for("student.feedback") + "#bug")
    mine_fb = Feedback.query.filter_by(user_id=current_user.id).order_by(Feedback.created_at.desc()).limit(5).all()
    mine_bugs = Defect.query.filter_by(reported_by=current_user.id).order_by(Defect.created_at.desc()).limit(5).all()
    return render_template("student/feedback.html", errors=errors, areas=FEEDBACK_AREAS, defect_types=DEFECT_TYPES,
                           mine_fb=mine_fb, mine_bugs=mine_bugs, form=request.form)
