"""Authentication: login (student/admin portals), registration with email OTP
verification, password recovery and logout.

Security notes
--------------
* The portal tab chosen on the login page is cosmetic. Permissions and the
  post-login redirect always come from ``User.role`` stored in the database.
* Public registration always creates ``role="student"``.
* Session is cleared before ``login_user`` (prevents session fixation) and the
  user id embeds ``session_version`` so password resets end other sessions.
"""
from __future__ import annotations

from datetime import timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template, request, session, url_for)
from flask_login import current_user, login_user, logout_user

from ..extensions import db, limiter
from ..models import EmailOTP, User
from ..security import dashboard_url_for, valid_email, valid_name, validate_password
from ..services.core import client_ip, get_bool_setting, log_action, notify
from ..services.email import EmailDeliveryError, delivery_mode, send_email
from ..services.tokens import (OTPError, find_reset_token, issue_reset_token, issue_verification_otp,
                               otp_send_wait_seconds, verify_otp)
from ..services.uploads import UploadError, save_image
from ..utils import clean_text, is_safe_url, normalize_email, utcnow

bp = Blueprint("auth", __name__)


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked = local[0] + "*"
    else:
        masked = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked}@{domain}"


def _start_session(user: User, remember: bool = False) -> None:
    """Regenerate the session and sign the user in."""
    session.clear()
    login_user(user, remember=remember)
    session.permanent = True
    user.last_login_at = utcnow()
    user.last_seen_at = utcnow()
    user.failed_logins = 0
    user.locked_until = None


def _redirect_after_login(user: User, portal: str | None = None):
    nxt = request.values.get("next")
    if nxt and is_safe_url(nxt):
        path = nxt.split("?")[0]
        allowed = not (path.startswith("/admin") and user.role != "admin") and not path.startswith("/auth")
        if allowed:
            return redirect(nxt)
    if portal == "admin" and user.role != "admin":
        flash("This is a student account, so you have been taken to the student dashboard.", "info")
    elif portal == "student" and user.role == "admin":
        flash("Signed in with an administrator account.", "info")
    return redirect(dashboard_url_for(user))


def _verify_user() -> User | None:
    uid = session.get("verify_uid")
    if uid:
        user = db.session.get(User, uid)
        if user and not user.is_verified:
            return user
    return None


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute; 60 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(dashboard_url_for(current_user))
    portal = request.values.get("portal", "student")
    portal = portal if portal in ("student", "admin") else "student"
    form = {"email": "", "remember": False}
    error = None

    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))
        form = {"email": email, "remember": remember}
        user = User.query.filter_by(email=email).first() if email else None
        cfg = current_app.config

        if not email or not password:
            error = "Enter your email address and password."
        elif user and user.is_locked:
            minutes = max(1, int((user.locked_until - utcnow()).total_seconds() // 60) + 1)
            error = (f"Too many failed attempts. Try again in about {minutes} minute(s), "
                     f"or reset your password.")
        elif user is None or not user.check_password(password):
            if user is not None:
                user.failed_logins = (user.failed_logins or 0) + 1
                if user.failed_logins >= cfg["LOGIN_MAX_FAILURES"]:
                    user.locked_until = utcnow() + timedelta(minutes=cfg["LOGIN_LOCK_MINUTES"])
                    user.failed_logins = 0
                    log_action("account_locked", "user", user.id, "Too many failed logins", user_id=user.id)
                log_action("login_failed", "user", user.id, f"portal={portal}", user_id=user.id)
                db.session.commit()
            error = "Incorrect email or password."
        elif not user.is_active_account:
            error = ("This account has been disabled. If you believe this is a mistake, contact support "
                     "through the Help page.")
            log_action("login_blocked_disabled", "user", user.id, user_id=user.id, commit=True)
        elif not user.is_verified:
            session["verify_uid"] = user.id
            active = EmailOTP.query.filter(EmailOTP.user_id == user.id, EmailOTP.consumed_at.is_(None),
                                           EmailOTP.invalidated_at.is_(None),
                                           EmailOTP.expires_at > utcnow()).first()
            if active is None and otp_send_wait_seconds(user) == 0:
                try:
                    mode = issue_verification_otp(user)
                    flash(f"Your email is not verified yet. We sent a new code to {_mask_email(user.email)}.",
                          "info")
                    if mode == "outbox":
                        session["dev_outbox_notice"] = True
                except OTPError as exc:
                    flash(exc.message, "error")
            else:
                flash("Please verify your email address to finish setting up your account.", "info")
            return redirect(url_for("auth.verify_email"))
        else:
            _start_session(user, remember)
            log_action("login", "user", user.id, f"role={user.role}; portal={portal}", user_id=user.id)
            db.session.commit()
            flash(f"Welcome back, {user.first_name}!", "success")
            return _redirect_after_login(user, portal)

    return render_template("auth/login.html", portal=portal, form=form, error=error,
                           next=request.values.get("next", ""))


@bp.route("/admin")
def admin_login():
    return redirect(url_for("auth.login", portal="admin", next=request.args.get("next") or None))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("6 per minute; 30 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(dashboard_url_for(current_user))
    registration_open = get_bool_setting("registration_open")
    form = {"full_name": "", "email": ""}
    errors: dict[str, str] = {}

    if request.method == "POST":
        if not registration_open:
            flash("New registrations are temporarily closed.", "error")
            return redirect(url_for("auth.register"))
        full_name = " ".join(clean_text(request.form.get("full_name"), 120).split())
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        form = {"full_name": full_name, "email": email}

        if not valid_name(full_name):
            errors["full_name"] = "Enter your full name (2–120 letters; no numbers or symbols)."
        if not valid_email(email):
            errors["email"] = "Enter a valid email address."
        pw_errors = validate_password(password, email, full_name)
        if pw_errors:
            errors["password"] = " ".join(pw_errors)
        if password != confirm:
            errors["confirm_password"] = "Passwords do not match."
        if not request.form.get("accept_terms"):
            errors["accept_terms"] = "You must accept the Terms and Privacy Policy to continue."

        existing = User.query.filter_by(email=email).first() if email else None
        if existing and existing.is_verified:
            errors["email"] = "An account with this email already exists. Sign in or reset your password."

        avatar_file = request.files.get("avatar")
        avatar_name = None
        if not errors and avatar_file and avatar_file.filename:
            try:
                avatar_name = save_image(avatar_file, "avatars", current_app.config["AVATAR_MAX_BYTES"], 400,
                                         square=True)
            except UploadError as exc:
                errors["avatar"] = str(exc)

        if not errors:
            if delivery_mode() == "unavailable":
                flash("Email delivery is not configured on this server, so accounts cannot be verified yet. "
                      "Please contact the administrator.", "error")
                return render_template("auth/register.html", form=form, errors=errors,
                                       registration_open=registration_open), 503
            if existing:  # unverified re-registration: refresh details, keep same record
                user = existing
                user.full_name = full_name
                user.set_password(password)
                if avatar_name:
                    user.avatar_filename = avatar_name
            else:
                user = User(full_name=full_name, email=email, role="student", avatar_filename=avatar_name)
                user.set_password(password)
                db.session.add(user)
            user.terms_accepted_at = utcnow()
            db.session.flush()
            log_action("register", "user", user.id, "Public registration (student)", user_id=user.id)
            db.session.commit()
            session.clear()
            session["verify_uid"] = user.id
            try:
                mode = issue_verification_otp(user, enforce_limits=bool(existing))
                if mode == "outbox":
                    session["dev_outbox_notice"] = True
                flash(f"Account created! We sent a 6-digit verification code to {_mask_email(email)}.", "success")
            except OTPError as exc:
                flash(f"Your account was created, but the verification email could not be sent: {exc.message}",
                      "error")
            return redirect(url_for("auth.verify_email"))

    return render_template("auth/register.html", form=form, errors=errors, registration_open=registration_open)


# ---------------------------------------------------------------------------
# Email OTP verification
# ---------------------------------------------------------------------------

@bp.route("/verify", methods=["GET", "POST"])
@limiter.limit("12 per minute", methods=["POST"])
def verify_email():
    if current_user.is_authenticated and current_user.is_verified:
        return redirect(dashboard_url_for(current_user))
    user = _verify_user()
    if user is None:
        flash("Sign in or create an account to verify your email address.", "info")
        return redirect(url_for("auth.login"))

    error = None
    if request.method == "POST":
        try:
            verify_otp(user, request.form.get("code", ""))
        except OTPError as exc:
            error = exc.message
        else:
            log_action("email_verified", "user", user.id, user_id=user.id)
            notify(user.id, "Welcome to QuizMaster! 🎉",
                   "Your email is verified. Explore quizzes and start tracking your growth.",
                   url_for("quiz.explore"), "success")
            _start_session(user)
            db.session.commit()
            flash("Email verified successfully. Welcome to QuizMaster!", "success")
            return redirect(dashboard_url_for(user))

    return render_template("auth/verify.html", email=_mask_email(user.email), error=error,
                           wait=otp_send_wait_seconds(user), ttl=current_app.config["OTP_TTL_MINUTES"],
                           dev_outbox=session.get("dev_outbox_notice") and delivery_mode() == "outbox")


@bp.route("/verify/resend", methods=["POST"])
@limiter.limit("4 per minute; 12 per hour")
def resend_otp():
    user = _verify_user()
    if user is None:
        return redirect(url_for("auth.login"))
    try:
        mode = issue_verification_otp(user)
        if mode == "outbox":
            session["dev_outbox_notice"] = True
        log_action("otp_resent", "user", user.id, user_id=user.id, commit=True)
        flash(f"A new code was sent to {_mask_email(user.email)}. Older codes no longer work.", "success")
    except OTPError as exc:
        flash(exc.message, "error")
    return redirect(url_for("auth.verify_email"))


@bp.route("/verify/cancel", methods=["POST"])
def cancel_verification():
    session.pop("verify_uid", None)
    session.pop("dev_outbox_notice", None)
    flash("Verification cancelled. You can register again with a different email address.", "info")
    return redirect(url_for("auth.register"))


# ---------------------------------------------------------------------------
# Password recovery
# ---------------------------------------------------------------------------

@bp.route("/forgot", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def forgot_password():
    sent = False
    error = None
    email = ""
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        if not valid_email(email):
            error = "Enter a valid email address."
        elif delivery_mode() == "unavailable":
            error = "Email delivery is not configured on this server. Please contact the administrator."
        else:
            user = User.query.filter_by(email=email).first()
            recent = False
            if user:
                from ..models import PasswordResetToken
                last = PasswordResetToken.query.filter_by(user_id=user.id) \
                    .order_by(PasswordResetToken.created_at.desc()).first()
                recent = bool(last and (utcnow() - last.created_at).total_seconds() < 60)
            if user and user.is_active_account and not recent:
                try:
                    mode = issue_reset_token(user, client_ip())
                    if mode == "outbox":
                        session["dev_outbox_notice"] = True
                    log_action("password_reset_requested", "user", user.id, user_id=user.id, commit=True)
                except EmailDeliveryError as exc:
                    error = str(exc)
            if not error:
                sent = True
    return render_template("auth/forgot.html", sent=sent, error=error, email=email,
                           dev_outbox=session.get("dev_outbox_notice") and delivery_mode() == "outbox",
                           ttl=current_app.config["RESET_TOKEN_TTL_MINUTES"])


@bp.route("/reset/<token>", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes", methods=["POST"])
def reset_password(token):
    rec = find_reset_token(token)
    if rec is None:
        return render_template("auth/reset.html", invalid=True), 400
    errors = {}
    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        user = rec.user
        pw_errors = validate_password(password, user.email, user.full_name)
        if pw_errors:
            errors["password"] = " ".join(pw_errors)
        elif password != confirm:
            errors["confirm_password"] = "Passwords do not match."
        elif user.check_password(password):
            errors["password"] = "Choose a password different from your current one."
        if not errors:
            user.set_password(password)
            user.session_version += 1          # signs out every existing session
            user.failed_logins = 0
            user.locked_until = None
            if not user.is_verified:
                user.email_verified_at = utcnow()  # possession of the inbox is proven
            rec.used_at = utcnow()
            log_action("password_reset", "user", user.id, "All sessions revoked", user_id=user.id)
            db.session.commit()
            try:
                send_email(user.email, "Your QuizMaster password was changed", "password_changed", user=user)
            except EmailDeliveryError:
                current_app.logger.warning("Password-changed notice could not be emailed to user %s", user.id)
            logout_user()
            session.clear()
            flash("Your password has been reset. Please sign in with your new password.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", invalid=False, token=token, errors=errors)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@bp.route("/logout", methods=["POST"])
def logout():
    if current_user.is_authenticated:
        log_action("logout", "user", current_user.id, commit=True)
    logout_user()
    session.clear()
    flash("You have been signed out securely.", "success")
    return redirect(url_for("public.home"))
