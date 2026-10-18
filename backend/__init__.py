"""QuizMaster application factory."""
from __future__ import annotations

import logging
import secrets
import time
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, session
from flask_login import current_user
from flask_wtf.csrf import CSRFError, generate_csrf
from werkzeug.exceptions import HTTPException

from .config import MIGRATIONS_DIR, STATIC_DIR, TEMPLATES_DIR, get_config

from .extensions import compress, csrf, db, limiter, login_manager, migrate
from .utils import fmt_dt, fmt_duration, iso_utc, time_ago, to_local, utc_to_local_input, utcnow

# Endpoints whose processing time is recorded as a TQM CTQ metric.
METRIC_ENDPOINTS = {"quiz.api_save", "quiz.api_submit", "quiz.api_state", "quiz.start"}


def create_app(config_object=None) -> Flask:
    # Frontend (Jinja templates, CSS, JS, images) lives in <root>/frontend; this package is the backend.
    app = Flask(__name__, instance_relative_config=False,
                template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR), static_url_path="/static")
    cfg = config_object or get_config()
    app.config.from_object(cfg)

    instance = Path(app.config["INSTANCE_DIR"])
    for sub in ("", "uploads/avatars", "uploads/questions", "backups", "logs"):
        (instance / sub).mkdir(parents=True, exist_ok=True)

    _ensure_secret_key(app, instance)
    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    _configure_logging(app, instance)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(MIGRATIONS_DIR), render_as_batch=True)
    csrf.init_app(app)
    limiter.init_app(app)
    compress.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "basic"

    from . import models  # noqa: F401  (register models with SQLAlchemy)

    @login_manager.user_loader
    def load_user(identity: str):
        try:
            uid, version = identity.split(":", 1)
            user = db.session.get(models.User, int(uid))
        except (ValueError, TypeError):
            return None
        if user is None or str(user.session_version) != version or not user.is_active_account:
            return None
        return user

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import flash, redirect, url_for
        from .security import json_error, wants_json
        if wants_json():
            return json_error("Your session has expired. Please sign in again.", 401, "unauthenticated")
        flash("Your session has ended or you are not signed in. Please sign in to continue.", "info")
        nxt = request.full_path if request.method == "GET" else None
        return redirect(url_for("auth.login", next=nxt))

    from .blueprints import register_blueprints
    register_blueprints(app)
    _register_hooks(app)
    _register_errors(app)
    _register_template_helpers(app)
    from .cli import register_cli
    register_cli(app)
    return app


def _ensure_secret_key(app: Flask, instance: Path) -> None:
    if app.config.get("SECRET_KEY"):
        return
    if app.config.get("APP_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in the environment for production.")
    # Development convenience: generate once and persist in instance/ (gitignored).
    key_file = instance / ".secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32), encoding="utf-8")
    app.config["SECRET_KEY"] = key_file.read_text(encoding="utf-8").strip()


def _configure_logging(app: Flask, instance: Path) -> None:
    if app.config.get("TESTING"):
        return
    handler = RotatingFileHandler(instance / "logs" / "quizmaster.log", maxBytes=1_000_000, backupCount=5,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_hooks(app: Flask) -> None:
    from .security import apply_security_headers

    @app.before_request
    def _before():
        g.request_started = time.perf_counter()
        g.csp_nonce = None
        if current_user.is_authenticated:
            session.permanent = True
            now = utcnow()
            if not current_user.last_seen_at or (now - current_user.last_seen_at).total_seconds() > 300:
                current_user.last_seen_at = now
                db.session.commit()
            if current_user.is_admin and request.endpoint and request.endpoint.startswith("admin."):
                from .services.backup import maybe_auto_backup
                maybe_auto_backup()

    @app.after_request
    def _after(response):
        response = apply_security_headers(response)
        started = g.get("request_started")
        if started and request.endpoint in METRIC_ENDPOINTS and not app.config.get("TESTING_SKIP_METRICS"):
            elapsed = (time.perf_counter() - started) * 1000
            response.headers["Server-Timing"] = f"app;dur={elapsed:.1f}"
            try:
                from .models import RequestMetric
                db.session.add(RequestMetric(endpoint=request.endpoint, method=request.method,
                                             status_code=response.status_code, duration_ms=round(elapsed, 3)))
                db.session.commit()
            except Exception:  # metrics must never break a request
                db.session.rollback()
        return response


def _log_error(exc: Exception, status: int) -> None:
    from .models import ErrorLog
    try:
        db.session.rollback()
        db.session.add(ErrorLog(
            path=request.path[:300], method=request.method, status_code=status,
            error_type=exc.__class__.__name__[:120], message=str(exc)[:1000],
            trace="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-6000:],
            user_id=current_user.id if current_user and current_user.is_authenticated else None,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _register_errors(app: Flask) -> None:
    from .security import wants_json

    def render(status: int, title: str, message: str):
        if wants_json():
            return jsonify({"ok": False, "error": {"code": str(status), "message": message}}), status
        return render_template("errors/error.html", status=status, title=title, message=message), status

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        return render(400, "Security check failed",
                      "Your form expired or the security token was missing. Refresh the page and try again.")

    @app.errorhandler(429)
    def too_many(e):
        return render(429, "Too many requests",
                      "You are doing that too often. Please wait a moment and try again.")

    @app.errorhandler(HTTPException)
    def http_error(e: HTTPException):
        messages = {
            400: ("Bad request", "The request could not be understood."),
            403: ("Access denied", "You do not have permission to view this page."),
            404: ("Page not found", "The page you are looking for does not exist or has moved."),
            405: ("Method not allowed", "This action is not allowed here."),
            413: ("File too large", "The uploaded file is larger than the permitted size."),
        }
        title, msg = messages.get(e.code, (e.name, e.description or "Something went wrong."))
        return render(e.code or 500, title, msg)

    @app.errorhandler(Exception)
    def unhandled(e: Exception):
        if isinstance(e, HTTPException):
            return http_error(e)
        app.logger.exception("Unhandled error on %s", request.path)
        _log_error(e, 500)
        if app.config.get("TESTING") and app.config.get("PROPAGATE_TEST_ERRORS", True):
            raise e
        return render(500, "Something went wrong",
                      "An unexpected error occurred. It has been logged for the QuizMaster team. "
                      "Please try again or go back to your dashboard.")


def _register_template_helpers(app: Flask) -> None:
    from .models import QUESTION_TYPES, RELEASE_POLICIES
    from .security import dashboard_url_for

    app.jinja_env.filters.update(dt=fmt_dt, duration=fmt_duration, ago=time_ago, iso=iso_utc, local=to_local,
                                  local_input=utc_to_local_input, pairs=lambda seq: [(x, x) for x in seq])
    from .icons import JS_ICONS, icon, logo_svg
    app.jinja_env.globals.update(icon=icon, logo_svg=logo_svg, JS_ICONS=JS_ICONS)
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    @app.context_processor
    def inject():
        from .services.core import get_setting
        prefs = current_user.prefs if current_user.is_authenticated else {}
        unread = 0
        if current_user.is_authenticated:
            from .models import Notification
            unread = Notification.query.filter_by(user_id=current_user.id, read_at=None).count()
        try:
            banner = get_setting("maintenance_banner")
        except Exception:
            banner = ""
        return {
            "csrf_token": generate_csrf,
            "app_name": app.config["APP_NAME"],
            "app_version": app.config["APP_VERSION"],
            "app_env": app.config["APP_ENV"],
            "home_url": dashboard_url_for(current_user),
            "user_prefs": prefs,
            "unread_count": unread,
            "QUESTION_TYPES": QUESTION_TYPES,
            "RELEASE_POLICIES": RELEASE_POLICIES,
            "maintenance_banner": banner,
            "now_utc": utcnow(),
        }
