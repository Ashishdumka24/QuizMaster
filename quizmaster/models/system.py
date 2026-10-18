"""Engagement (notifications, announcements, feedback, support) and system
records (audit log, settings, error log, request metrics)."""
from __future__ import annotations

from ..extensions import db
from ..utils import utcnow


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.String(500))
    link = db.Column(db.String(300))
    kind = db.Column(db.String(20), nullable=False, default="info")
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    audience = db.Column(db.String(10), nullable=False, default="all")  # all | students | admins
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    pinned = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    author = db.relationship("User")


class Feedback(db.Model):
    """In-app customer feedback (TQM: Customer Focus / Q08 / Q19)."""

    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    rating = db.Column(db.Integer, nullable=False)
    area = db.Column(db.String(30), nullable=False, default="general")
    message = db.Column(db.Text)
    status = db.Column(db.String(15), nullable=False, default="new")  # new | reviewed | actioned
    admin_note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User")

    __table_args__ = (db.CheckConstraint("rating >= 1 AND rating <= 5", name="rating_range"),)


class SupportMessage(db.Model):
    __tablename__ = "support_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(15), nullable=False, default="open")  # open | answered | closed
    admin_note = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    entity_type = db.Column(db.String(40))
    entity_id = db.Column(db.String(40))
    details = db.Column(db.String(1000))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User")


class Setting(db.Model):
    __tablename__ = "settings"

    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class ErrorLog(db.Model):
    """Unhandled server errors captured automatically (Q09 / Q18)."""

    __tablename__ = "error_logs"

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(300))
    method = db.Column(db.String(10))
    status_code = db.Column(db.Integer)
    error_type = db.Column(db.String(120))
    message = db.Column(db.String(1000))
    trace = db.Column(db.Text)
    user_id = db.Column(db.Integer)
    resolved = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class RequestMetric(db.Model):
    """Server processing time for quiz-engine API calls (CTQ: zero-latency submissions)."""

    __tablename__ = "request_metrics"

    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(80), nullable=False, index=True)
    method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    duration_ms = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
