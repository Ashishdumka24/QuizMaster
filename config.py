"""
QuizMaster configuration.

All secrets and service settings are read from environment variables
(optionally loaded from a local `.env` file). Never hard-code credentials here.
See `.env.example` for the complete list of supported variables.
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    APP_NAME = "QuizMaster"
    APP_VERSION = "1.0.0"
    APP_ENV = os.environ.get("APP_ENV", "development").lower()
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    # When APP_BASE_URL is not set explicitly (local dev / preview), links in
    # emails use the host of the current request instead. Always set it in
    # production so links can never be influenced by a forged Host header.
    APP_BASE_URL_EXPLICIT = bool(os.environ.get("APP_BASE_URL"))

    # --- Core security -----------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY") or ""
    # HMAC pepper for OTP / reset-token hashes (falls back to SECRET_KEY).
    TOKEN_PEPPER = os.environ.get("TOKEN_PEPPER") or ""

    # --- Database ----------------------------------------------------------
    INSTANCE_DIR = Path(os.environ.get("INSTANCE_DIR", BASE_DIR / "instance"))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'instance' / 'quizmaster.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Sessions & cookies --------------------------------------------------
    SESSION_COOKIE_NAME = "qm_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
    # Who may embed the site in an iframe. Production default: same origin only.
    FRAME_ANCESTORS = os.environ.get("FRAME_ANCESTORS", "")
    # Set TRUST_PROXY=1 when running behind a reverse proxy (nginx, Render, etc.)
    TRUST_PROXY = _bool("TRUST_PROXY", False)
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=_int("REMEMBER_DAYS", 14))
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=_int("SESSION_LIFETIME_MINUTES", 120))
    SESSION_REFRESH_EACH_REQUEST = True

    # --- CSRF ----------------------------------------------------------------
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # token valid for the life of the session
    WTF_CSRF_HEADERS = ["X-CSRFToken", "X-CSRF-Token"]

    # --- Rate limiting -------------------------------------------------------
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", True)

    # --- Email (SMTP) --------------------------------------------------------
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = _int("MAIL_PORT", 587)
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")
    MAIL_TIMEOUT = _int("MAIL_TIMEOUT", 20)
    # Development-only email preview (writes emails to instance/outbox instead
    # of sending). Automatically disabled when APP_ENV=production.
    MAIL_DEV_OUTBOX = _bool("MAIL_DEV_OUTBOX", True)
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "")

    # --- OTP / tokens --------------------------------------------------------
    OTP_LENGTH = 6
    OTP_TTL_MINUTES = _int("OTP_TTL_MINUTES", 10)
    OTP_MAX_ATTEMPTS = _int("OTP_MAX_ATTEMPTS", 5)
    OTP_RESEND_COOLDOWN_SECONDS = _int("OTP_RESEND_COOLDOWN_SECONDS", 60)
    OTP_MAX_SENDS_PER_HOUR = _int("OTP_MAX_SENDS_PER_HOUR", 5)
    RESET_TOKEN_TTL_MINUTES = _int("RESET_TOKEN_TTL_MINUTES", 30)
    LOGIN_MAX_FAILURES = _int("LOGIN_MAX_FAILURES", 5)
    LOGIN_LOCK_MINUTES = _int("LOGIN_LOCK_MINUTES", 15)

    # --- Uploads -------------------------------------------------------------
    MAX_CONTENT_LENGTH = _int("MAX_UPLOAD_MB", 5) * 1024 * 1024
    AVATAR_MAX_BYTES = 2 * 1024 * 1024
    QUESTION_IMAGE_MAX_BYTES = 3 * 1024 * 1024
    IMPORT_MAX_BYTES = 1 * 1024 * 1024
    IMPORT_MAX_ROWS = 500

    # --- Quiz engine ----------------------------------------------------------
    SUBMISSION_GRACE_SECONDS = _int("SUBMISSION_GRACE_SECONDS", 10)

    # --- Backups / maintenance ------------------------------------------------
    AUTO_BACKUP_ENABLED = _bool("AUTO_BACKUP_ENABLED", True)
    BACKUP_KEEP = _int("BACKUP_KEEP", 14)
    STATS_CACHE_SECONDS = _int("STATS_CACHE_SECONDS", 30)

    # --- Compression ---------------------------------------------------------
    COMPRESS_MIMETYPES = [
        "text/html", "text/css", "application/javascript", "text/javascript",
        "application/json", "image/svg+xml", "text/csv",
    ]
    COMPRESS_MIN_SIZE = 600

    TESTING = False
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = _bool("FLASK_DEBUG", True)


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    MAIL_DEV_OUTBOX = False
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    MAIL_DEV_OUTBOX = True
    AUTO_BACKUP_ENABLED = False
    STATS_CACHE_SECONDS = 0


def get_config():
    env = os.environ.get("APP_ENV", "development").lower()
    return {"production": ProductionConfig, "testing": TestingConfig}.get(env, DevelopmentConfig)
