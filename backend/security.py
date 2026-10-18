"""Authorisation decorators, API response helpers, password policy and headers."""
from __future__ import annotations

import re
from functools import wraps

from flask import abort, current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user

COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890", "qwerty123",
    "iloveyou", "admin123", "welcome1", "letmein1", "quizmaster", "qwertyuiop", "11111111",
    "abc12345", "passw0rd", "football", "baseball", "sunshine1", "princess1",
}


def wants_json() -> bool:
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json" \
        or request.headers.get("X-Requested-With") == "fetch"


def json_ok(data=None, message: str | None = None, status: int = 200, **extra):
    payload = {"ok": True, "data": data if data is not None else {}}
    if message:
        payload["message"] = message
    payload.update(extra)
    return jsonify(payload), status


def json_error(message: str, status: int = 400, code: str = "error", fields: dict | None = None, **extra):
    payload = {"ok": False, "error": {"code": code, "message": message}}
    if fields:
        payload["error"]["fields"] = fields
    payload.update(extra)
    return jsonify(payload), status


def role_required(*roles):
    """Server-side role check. The role always comes from the database record
    loaded by Flask-Login, never from anything the browser sends."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                if wants_json():
                    return json_error("Your session has expired. Please sign in again.", 401, "unauthenticated")
                flash("Please sign in to continue.", "info")
                return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
            if not current_user.is_verified:
                if wants_json():
                    return json_error("Please verify your email address first.", 403, "unverified")
                return redirect(url_for("auth.verify_email"))
            if roles and current_user.role not in roles:
                if wants_json():
                    return json_error("You do not have permission to perform this action.", 403, "forbidden")
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


login_required_verified = role_required()
student_required = role_required("student")
admin_required = role_required("admin")


def dashboard_url_for(user) -> str:
    if user and getattr(user, "is_authenticated", False):
        return url_for("admin.overview") if user.role == "admin" else url_for("student.dashboard")
    return url_for("public.home")


def validate_password(password: str, email: str = "", name: str = "") -> list[str]:
    """Pragmatic policy: long passphrases welcome, no arbitrary composition rules
    beyond requiring a mix for shorter passwords (NIST SP 800-63B inspired)."""
    errors = []
    pw = password or ""
    if len(pw) < 8:
        errors.append("Use at least 8 characters.")
    if len(pw) > 128:
        errors.append("Use at most 128 characters.")
    if pw.lower() in COMMON_PASSWORDS:
        errors.append("This password is too common. Choose something less predictable.")
    local = (email or "").split("@")[0].lower()
    if local and len(local) >= 4 and local in pw.lower():
        errors.append("Do not include your email address in the password.")
    if len(pw) < 12:
        classes = sum(bool(re.search(p, pw)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
        if classes < 3:
            errors.append("Passwords shorter than 12 characters need 3 of: lowercase, uppercase, number, symbol.")
    return errors


def password_strength(password: str) -> int:
    """0-4 score mirrored by the frontend meter."""
    pw = password or ""
    score = 0
    if len(pw) >= 8:
        score += 1
    if len(pw) >= 12:
        score += 1
    if re.search(r"[a-z]", pw) and re.search(r"[A-Z]", pw):
        score += 1
    if re.search(r"\d", pw) and re.search(r"[^A-Za-z0-9]", pw):
        score += 1
    return min(score, 4)


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-']+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def valid_email(email: str) -> bool:
    return bool(email) and len(email) <= 254 and bool(EMAIL_RE.match(email))


NAME_RE = re.compile(r"^[^\d<>{}\[\]\\/@#$%^*=+_|~`\"]{2,120}$")


def valid_name(name: str) -> bool:
    return bool(NAME_RE.match((name or "").strip()))


def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    production = current_app.config.get("APP_ENV") == "production"
    frame_ancestors = current_app.config.get("FRAME_ANCESTORS") or ("'self'" if production else "*")
    if frame_ancestors == "'self'":
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; "
        f"frame-ancestors {frame_ancestors}; base-uri 'self'; form-action 'self'",
    )
    if current_app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.path.startswith(("/api/", "/auth/", "/admin", "/account")) or response.mimetype == "application/json":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def safe_back(default: str) -> str:
    """Return the Referer only when it points at this same host (prevents open redirects)."""
    from urllib.parse import urlparse
    from flask import request
    ref = request.referrer
    if ref:
        parsed = urlparse(ref)
        if parsed.netloc == request.host and parsed.scheme in ("http", "https"):
            return parsed.path + (("?" + parsed.query) if parsed.query else "")
    return default
