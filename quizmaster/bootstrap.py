"""Start-up helpers used by app.py (development) and deployment scripts."""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from .extensions import db


def prepare_database(app: Flask) -> None:
    """Apply migrations, seed base content and bootstrap the first admin."""
    migrations = Path(app.root_path).parent / "migrations"
    if migrations.exists():
        from flask_migrate import upgrade
        upgrade(directory=str(migrations))
    else:  # pragma: no cover - fallback when migrations folder is absent
        db.create_all()

    from .models import User
    from .seed import seed_all
    report = seed_all()
    if any(report.values()):
        app.logger.info("Seeded base content: %s", report)

    if not User.query.filter_by(role="admin").first():
        email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
        if email and password:
            from .security import validate_password
            from .utils import utcnow
            problems = validate_password(password, email)
            if problems:
                print(f"  ! INITIAL_ADMIN_PASSWORD rejected: {' '.join(problems)}")
            else:
                admin = User(full_name=os.environ.get("INITIAL_ADMIN_NAME", "QuizMaster Admin"), email=email,
                             role="admin", email_verified_at=utcnow(), terms_accepted_at=utcnow())
                admin.set_password(password)
                db.session.add(admin)
                db.session.commit()
                print(f"  ✔ First administrator created: {email} (remove INITIAL_ADMIN_PASSWORD from .env now)")
        else:
            print("\n  ! No administrator account exists yet. Create one with:\n"
                  "      flask --app app create-admin\n")
