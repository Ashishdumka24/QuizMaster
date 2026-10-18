"""SQLite backups (Q01 Auto Backup / Q20). Uses SQLite's online backup API so a
consistent copy is taken even while the application is running.

For PostgreSQL deployments use `pg_dump` (see docs/DEPLOYMENT.md).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..utils import utcnow
from .core import get_setting, set_setting


class BackupError(Exception):
    pass


def backup_dir() -> Path:
    path = Path(current_app.config["INSTANCE_DIR"]) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sqlite_path() -> Path | None:
    url = db.engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return Path(url.database)


def create_backup(label: str = "manual") -> Path:
    src = _sqlite_path()
    if src is None:
        raise BackupError("In-app backups support SQLite only. Use pg_dump for PostgreSQL.")
    name = f"quizmaster-{utcnow().strftime('%Y%m%d-%H%M%S')}-{label}.db"
    dest = backup_dir() / name
    db.session.commit()
    with sqlite3.connect(src) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    prune_backups()
    return dest


def prune_backups() -> None:
    keep = int(current_app.config.get("BACKUP_KEEP", 14))
    files = sorted(backup_dir().glob("quizmaster-*.db"), reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def list_backups() -> list[dict]:
    out = []
    for f in sorted(backup_dir().glob("quizmaster-*.db"), reverse=True):
        st = f.stat()
        out.append({"name": f.name, "size_kb": round(st.st_size / 1024, 1), "mtime": st.st_mtime,
                    "created": datetime.fromtimestamp(st.st_mtime, timezone.utc).replace(tzinfo=None),
                    "kind": "auto" if f.stem.endswith("-auto") else "manual"})
    return out


def resolve_backup(name: str) -> Path | None:
    safe = Path(name).name
    if safe != name or not safe.startswith("quizmaster-") or not safe.endswith(".db"):
        return None
    path = backup_dir() / safe
    return path if path.exists() else None


def maybe_auto_backup() -> Path | None:
    """Called opportunistically (at most once per configured interval)."""
    if not current_app.config.get("AUTO_BACKUP_ENABLED") or _sqlite_path() is None:
        return None
    try:
        hours = max(1, int(get_setting("auto_backup_hours") or 24))
    except ValueError:
        hours = 24
    last = get_setting("last_auto_backup") or ""
    now = utcnow()
    if last:
        try:
            from datetime import datetime
            if now - datetime.fromisoformat(last) < timedelta(hours=hours):
                return None
        except ValueError:
            pass
    set_setting("last_auto_backup", now.isoformat())
    db.session.commit()
    try:
        return create_backup("auto")
    except Exception as exc:  # pragma: no cover - disk errors
        current_app.logger.error("Automatic backup failed: %s", exc)
        return None


def restore_backup(path: Path) -> None:
    """CLI-only restore: copies a backup over the live database."""
    dest = _sqlite_path()
    if dest is None:
        raise BackupError("Restore supports SQLite only.")
    create_backup("pre-restore")
    db.session.remove()
    db.engine.dispose()
    with sqlite3.connect(path) as source, sqlite3.connect(dest) as target:
        source.backup(target)
