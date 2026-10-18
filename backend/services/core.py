"""Cross-cutting services: audit trail, persisted settings, notifications, cache."""
from __future__ import annotations

import json
import threading
import time

from flask import has_request_context, request
from flask_login import current_user

from ..extensions import db
from ..models import AuditLog, Notification, Setting, User

# ---------------------------------------------------------------------------
# Audit trail (Q01 / Q04 / Q07 / Q11)
# ---------------------------------------------------------------------------


def client_ip() -> str | None:
    if not has_request_context():
        return None
    return (request.remote_addr or "")[:64] or None


def log_action(action: str, entity_type: str | None = None, entity_id=None, details: str | None = None,
               user_id: int | None = None, commit: bool = False) -> None:
    if user_id is None and has_request_context() and current_user and current_user.is_authenticated:
        user_id = current_user.id
    db.session.add(AuditLog(
        user_id=user_id, action=action[:60], entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=(details or "")[:1000] or None, ip_address=client_ip(),
    ))
    if commit:
        db.session.commit()


# ---------------------------------------------------------------------------
# Persisted application settings (admin → Settings)
# ---------------------------------------------------------------------------

SETTING_DEFAULTS = {
    "site_tagline": "Challenge Your Mind. Track Your Growth. Master Every Quiz.",
    "registration_open": "true",
    "maintenance_banner": "",
    "default_time_limit": "15",
    "default_pass_percentage": "40",
    "leaderboard_enabled": "true",
    "auto_backup_hours": "24",
    "last_auto_backup": "",
    "support_hours": "Monday–Saturday, 9:00 AM – 6:00 PM IST",
}


def get_setting(key: str, default: str | None = None) -> str:
    row = db.session.get(Setting, key)
    if row is not None and row.value is not None:
        return row.value
    return SETTING_DEFAULTS.get(key, default) if default is None else default


def get_bool_setting(key: str) -> bool:
    return str(get_setting(key)).lower() in ("1", "true", "yes", "on")


def set_setting(key: str, value) -> None:
    row = db.session.get(Setting, key)
    if row is None:
        row = Setting(key=key)
        db.session.add(row)
    row.value = "" if value is None else str(value)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def notify(user_id: int, title: str, body: str = "", link: str | None = None, kind: str = "info") -> None:
    db.session.add(Notification(user_id=user_id, title=title[:150], body=(body or "")[:500], link=link, kind=kind))


def notify_role(role: str | None, title: str, body: str = "", link: str | None = None, kind: str = "info") -> int:
    q = User.query.filter(User.is_active_account.is_(True), User.email_verified_at.isnot(None))
    if role:
        q = q.filter(User.role == role)
    count = 0
    for (uid,) in q.with_entities(User.id).all():
        notify(uid, title, body, link, kind)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Tiny thread-safe TTL cache for expensive dashboard aggregates (Q05 / Q17)
# ---------------------------------------------------------------------------


class TTLCache:
    def __init__(self):
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: str, ttl: int, factory):
        now = time.monotonic()
        if ttl > 0:
            with self._lock:
                hit = self._data.get(key)
                if hit and hit[0] > now:
                    return hit[1]
        value = factory()
        if ttl > 0:
            with self._lock:
                self._data[key] = (now + ttl, value)
        return value

    def clear(self, prefix: str = "") -> None:
        with self._lock:
            for k in [k for k in self._data if k.startswith(prefix)]:
                self._data.pop(k, None)


cache = TTLCache()


def dumps(data) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
