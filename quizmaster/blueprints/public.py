"""Public pages: homepage, about, help/FAQ/contact, legal, changelog, media, health."""
from __future__ import annotations

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, send_file,
                   send_from_directory, url_for)
from flask_login import current_user
from sqlalchemy import func, text

from ..extensions import db, limiter
from ..models import Category, ChangelogEntry, Quiz, QuizAttempt, SupportMessage, User
from ..security import valid_email, valid_name
from ..services.core import get_setting, log_action, notify_role
from ..services.email import EmailDeliveryError, delivery_mode, list_outbox, outbox_dir, send_email
from ..services.stats import published_open_quizzes
from ..services.uploads import upload_dir
from ..utils import clean_text, normalize_email

bp = Blueprint("public", __name__)


@bp.route("/")
def home():
    featured = published_open_quizzes().order_by(Quiz.featured.desc(), Quiz.published_at.desc()).limit(6).all()
    featured = [q for q in featured if q.question_count > 0]
    categories = (db.session.query(Category, func.count(Quiz.id))
                  .outerjoin(Quiz, (Quiz.category_id == Category.id) & (Quiz.status == "published"))
                  .group_by(Category.id).order_by(func.count(Quiz.id).desc(), Category.name).all())
    platform = {
        "quizzes": Quiz.query.filter_by(status="published").count(),
        "categories": Category.query.count(),
        "attempts": QuizAttempt.query.filter(QuizAttempt.status.in_(("submitted", "expired"))).count(),
        "learners": User.query.filter(User.role == "student", User.email_verified_at.isnot(None)).count(),
    }
    return render_template("public/home.html", featured=featured, categories=categories, platform=platform,
                           tagline=get_setting("site_tagline"))


@bp.route("/about")
def about():
    return render_template("public/about.html")


@bp.route("/help", methods=["GET", "POST"])
@limiter.limit("5 per 10 minutes", methods=["POST"])
def help_center():
    form = {"name": "", "email": "", "subject": "", "message": ""}
    errors = {}
    if current_user.is_authenticated:
        form.update(name=current_user.full_name, email=current_user.email)
    if request.method == "POST":
        form = {k: clean_text(request.form.get(k), 4000 if k == "message" else 150) for k in form}
        form["email"] = normalize_email(form["email"])
        if not valid_name(form["name"]):
            errors["name"] = "Enter your name."
        if not valid_email(form["email"]):
            errors["email"] = "Enter a valid email address."
        if len(form["subject"]) < 3:
            errors["subject"] = "Enter a short subject (3+ characters)."
        if len(form["message"]) < 10:
            errors["message"] = "Please describe your question in at least 10 characters."
        if not errors:
            msg = SupportMessage(user_id=current_user.id if current_user.is_authenticated else None, **form)
            db.session.add(msg)
            db.session.flush()
            notify_role("admin", "New support message", f"{form['subject']} — from {form['name']}",
                        url_for("admin.inbox"), "info")
            log_action("support_message", "support", msg.id, form["subject"])
            db.session.commit()
            support = current_app.config.get("SUPPORT_EMAIL")
            if support and delivery_mode() == "smtp":
                try:
                    send_email(support, f"[QuizMaster support] {form['subject']}", "support_notice", msg=msg)
                except EmailDeliveryError:
                    current_app.logger.warning("Support notice email failed for message %s", msg.id)
            flash("Thanks! Your message has been saved and our team will reply by email. "
                  f"Reference #{msg.id}.", "success")
            return redirect(url_for("public.help_center") + "#contact")
    return render_template("public/help.html", form=form, errors=errors, support_hours=get_setting("support_hours"))


@bp.route("/help/manual")
def manual():
    return render_template("public/manual.html")


@bp.route("/privacy")
def privacy():
    return render_template("public/legal.html", page="privacy")


@bp.route("/terms")
def terms():
    return render_template("public/legal.html", page="terms")


@bp.route("/changelog")
def changelog():
    entries = ChangelogEntry.query.order_by(ChangelogEntry.released_on.desc(), ChangelogEntry.id.desc()).all()
    return render_template("public/changelog.html", entries=entries)


@bp.route("/shortcuts")
def shortcuts():
    return render_template("public/shortcuts.html")


# ---------------------------------------------------------------------------
# Uploaded media (served from instance/uploads, never from /static)
# ---------------------------------------------------------------------------

@bp.route("/media/<kind>/<path:filename>")
def media(kind, filename):
    if kind not in ("avatars", "questions"):
        abort(404)
    if kind == "questions" and not current_user.is_authenticated:
        abort(404)
    if "/" in filename or "\\" in filename or not filename.endswith(".webp"):
        abort(404)
    response = send_from_directory(upload_dir(kind), filename, mimetype="image/webp", max_age=86400)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.route("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        ok = True
    except Exception:
        ok = False
    return jsonify({"status": "ok" if ok else "degraded", "database": ok,
                    "version": current_app.config["APP_VERSION"],
                    "email_mode": delivery_mode()}), (200 if ok else 503)


# ---------------------------------------------------------------------------
# Development-only email outbox (disabled in production and when SMTP is set)
# ---------------------------------------------------------------------------

@bp.route("/dev/outbox")
def dev_outbox():
    if delivery_mode() != "outbox":
        abort(404)
    return render_template("public/dev_outbox.html", items=list_outbox())


@bp.route("/dev/outbox/<path:filename>")
def dev_outbox_message(filename):
    if delivery_mode() != "outbox" or "/" in filename or not filename.endswith(".html"):
        abort(404)
    path = outbox_dir() / filename
    if not path.exists():
        abort(404)
    resp = send_file(path, mimetype="text/html")
    resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    return resp
