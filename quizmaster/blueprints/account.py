"""Profile, photo upload, password change, preferences and privacy controls
(shared by students and administrators – users may only edit their own account)."""
from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from ..extensions import db, limiter
from ..models import QuizAttempt, User
from ..security import json_error, json_ok, login_required_verified, valid_name, validate_password
from ..services.core import cache, log_action
from ..services.stats import student_stats
from ..services.uploads import UploadError, delete_upload, save_image
from ..utils import clean_text, to_int

bp = Blueprint("account", __name__)

PALETTES = {"aurora": "Aurora (violet → cyan)", "ocean": "Ocean (blue → teal)",
            "sunset": "Sunset (coral → amber)", "forest": "Forest (emerald → lime)"}


@bp.route("/profile", methods=["GET", "POST"])
@login_required_verified
def profile():
    errors = {}
    if request.method == "POST":
        name = " ".join(clean_text(request.form.get("full_name"), 120).split())
        if not valid_name(name):
            errors["full_name"] = "Enter your full name (2–120 letters)."
        phone = clean_text(request.form.get("phone"), 20)
        digits = "".join(c for c in phone if c.isdigit())
        if phone and not (7 <= len(digits) <= 15):
            errors["phone"] = "Enter a valid phone number (7–15 digits)."
        if not errors:
            current_user.full_name = name
            current_user.bio = clean_text(request.form.get("bio"), 500) or None
            current_user.institution = clean_text(request.form.get("institution"), 150) or None
            current_user.program = clean_text(request.form.get("program"), 120) or None
            current_user.phone = phone or None
            log_action("profile_updated", "user", current_user.id)
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("account.profile"))
    stats = student_stats(current_user) if current_user.role == "student" else None
    recent = (QuizAttempt.query.filter_by(user_id=current_user.id).order_by(QuizAttempt.started_at.desc())
              .limit(5).all())
    return render_template("account/profile.html", errors=errors, stats=stats, recent=recent)


@bp.route("/avatar", methods=["POST"])
@login_required_verified
@limiter.limit("10 per hour")
def avatar_upload():
    try:
        name = save_image(request.files.get("avatar"), "avatars", current_app.config["AVATAR_MAX_BYTES"], 400,
                          square=True)
    except UploadError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return json_error(str(exc), 400, "upload")
        flash(str(exc), "error")
        return redirect(url_for("account.profile"))
    old = current_user.avatar_filename
    current_user.avatar_filename = name
    log_action("avatar_updated", "user", current_user.id)
    db.session.commit()
    delete_upload("avatars", old)
    if request.headers.get("X-Requested-With") == "fetch":
        return json_ok({"url": url_for("public.media", kind="avatars", filename=name)}, "Profile photo updated.")
    flash("Profile photo updated.", "success")
    return redirect(url_for("account.profile"))


@bp.route("/avatar/delete", methods=["POST"])
@login_required_verified
def avatar_delete():
    old = current_user.avatar_filename
    current_user.avatar_filename = None
    log_action("avatar_removed", "user", current_user.id)
    db.session.commit()
    delete_upload("avatars", old)
    flash("Profile photo removed.", "success")
    return redirect(url_for("account.profile"))


@bp.route("/security", methods=["GET", "POST"])
@login_required_verified
@limiter.limit("8 per 15 minutes", methods=["POST"])
def security():
    errors = {}
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        if not current_user.check_password(current):
            errors["current_password"] = "Your current password is incorrect."
        else:
            pw = validate_password(new, current_user.email, current_user.full_name)
            if pw:
                errors["new_password"] = " ".join(pw)
            elif new != confirm:
                errors["confirm_password"] = "Passwords do not match."
            elif current == new:
                errors["new_password"] = "The new password must be different."
        if not errors:
            current_user.set_password(new)
            current_user.session_version += 1  # sign out other devices
            log_action("password_changed", "user", current_user.id, "Other sessions revoked")
            db.session.commit()
            session.clear()
            login_user(current_user)  # keep this device signed in with the new session version
            session.permanent = True
            flash("Password changed. Other devices have been signed out.", "success")
            return redirect(url_for("account.security"))
    return render_template("account/security.html", errors=errors)


@bp.route("/sessions/revoke", methods=["POST"])
@login_required_verified
def revoke_sessions():
    current_user.session_version += 1
    log_action("sessions_revoked", "user", current_user.id)
    db.session.commit()
    logout_user()
    session.clear()
    flash("You have been signed out on all devices. Please sign in again.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/settings", methods=["GET", "POST"])
@login_required_verified
def settings():
    if request.method == "POST":
        prefs = _prefs_from(request.form)
        current_user.set_prefs(**prefs)
        log_action("preferences_updated", "user", current_user.id)
        db.session.commit()
        flash("Preferences saved.", "success")
        return redirect(url_for("account.settings"))
    return render_template("account/settings.html", palettes=PALETTES)


def _prefs_from(data) -> dict:
    out = {}
    if data.get("theme") in ("light", "dark", "system"):
        out["theme"] = data.get("theme")
    if data.get("palette") in PALETTES:
        out["palette"] = data.get("palette")
    if data.get("contrast") in ("normal", "high"):
        out["contrast"] = data.get("contrast")
    scale = to_int(data.get("font_scale"), None, 85, 130)
    if scale:
        out["font_scale"] = scale
    # Checkboxes: when the full settings form is submitted, an absent box means False.
    if data.get("_full_form"):
        out["reduce_motion"] = bool(data.get("reduce_motion"))
        out["leaderboard_visible"] = bool(data.get("leaderboard_visible"))
        out["email_notifications"] = bool(data.get("email_notifications"))
    return out


@bp.route("/api/prefs", methods=["POST"])
@login_required_verified
def api_prefs():
    """Quick toggles (theme switch, font size) from the top bar."""
    data = request.get_json(silent=True) or {}
    prefs = _prefs_from(data)
    if "reduce_motion" in data:
        prefs["reduce_motion"] = bool(data["reduce_motion"])
    if not prefs:
        return json_error("No valid preference supplied.")
    current_user.set_prefs(**prefs)
    db.session.commit()
    return json_ok(current_user.prefs)


@bp.route("/delete", methods=["POST"])
@login_required_verified
@limiter.limit("5 per hour")
def delete_account():
    if not current_user.check_password(request.form.get("password") or ""):
        flash("Account not deleted: the password you entered is incorrect.", "error")
        return redirect(url_for("account.settings") + "#danger")
    if current_user.role == "admin" and User.query.filter_by(role="admin", is_active_account=True).count() <= 1:
        flash("You are the only active administrator and cannot delete your account.", "error")
        return redirect(url_for("account.settings") + "#danger")
    uid, avatar = current_user.id, current_user.avatar_filename
    log_action("account_deleted", "user", uid, "Self-service deletion", user_id=None)
    user = db.session.get(User, uid)
    logout_user()
    db.session.delete(user)
    db.session.commit()
    delete_upload("avatars", avatar)
    cache.clear()
    session.clear()
    flash("Your account and quiz history have been permanently deleted.", "success")
    return redirect(url_for("public.home"))
