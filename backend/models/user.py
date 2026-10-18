"""User accounts, email verification and password-reset records."""
from __future__ import annotations

import json

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..utils import utcnow

ROLE_STUDENT = "student"
ROLE_ADMIN = "admin"
ROLES = (ROLE_STUDENT, ROLE_ADMIN)

DEFAULT_PREFS = {
    "theme": "system",        # light | dark | system
    "palette": "aurora",      # aurora | ocean | sunset | forest
    "contrast": "normal",     # normal | high
    "font_scale": 100,        # 90..130 (%)
    "reduce_motion": False,
    "leaderboard_visible": True,
    "email_notifications": True,
}


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT, index=True)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    email_verified_at = db.Column(db.DateTime)
    avatar_filename = db.Column(db.String(80))
    bio = db.Column(db.String(500))
    institution = db.Column(db.String(150))
    program = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    preferences = db.Column(db.Text)
    session_version = db.Column(db.Integer, nullable=False, default=1)
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    last_seen_at = db.Column(db.DateTime)
    terms_accepted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    attempts = db.relationship("QuizAttempt", back_populates="user", lazy="dynamic",
                               cascade="all, delete-orphan")

    __table_args__ = (db.CheckConstraint("role in ('student','admin')", name="role_valid"),)

    # ---- passwords ----------------------------------------------------------
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        try:
            return check_password_hash(self.password_hash, password)
        except Exception:
            return False

    # ---- Flask-Login --------------------------------------------------------
    def get_id(self) -> str:
        # Embedding the session version means bumping it (password reset,
        # "sign out everywhere", deactivation) invalidates all existing sessions.
        return f"{self.id}:{self.session_version}"

    @property
    def is_active(self) -> bool:  # used by Flask-Login
        return bool(self.is_active_account)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def first_name(self) -> str:
        return (self.full_name or "").split(" ")[0] or "there"

    @property
    def initials(self) -> str:
        parts = [p for p in (self.full_name or "?").split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "?"

    @property
    def public_name(self) -> str:
        """Privacy-friendly display name for leaderboards (e.g. "Asha K.")."""
        parts = [p for p in (self.full_name or "").split() if p]
        if not parts:
            return "Anonymous"
        return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."

    @property
    def prefs(self) -> dict:
        data = dict(DEFAULT_PREFS)
        try:
            data.update(json.loads(self.preferences or "{}"))
        except (ValueError, TypeError):
            pass
        return data

    def set_prefs(self, **changes) -> None:
        data = self.prefs
        data.update(changes)
        self.preferences = json.dumps(data)

    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > utcnow())

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.id} {self.email} {self.role}>"


class EmailOTP(db.Model):
    """One-time codes for email verification. Only an HMAC of the code is stored."""

    __tablename__ = "email_otps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = db.Column(db.String(20), nullable=False, default="verify")
    code_hash = db.Column(db.String(128), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed_at = db.Column(db.DateTime)
    invalidated_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User")


class PasswordResetToken(db.Model):
    """Single-use, time-limited password reset tokens (stored as SHA-256/HMAC hash)."""

    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    request_ip = db.Column(db.String(64))

    user = db.relationship("User")
