"""Flask CLI commands.

    flask --app app create-admin            # interactive, secure first admin
    flask --app app seed                    # categories + sample quizzes + TQM baseline records
    flask --app app backup                  # SQLite backup into instance/backups
    flask --app app restore-backup FILE     # restore (creates a pre-restore backup first)
    flask --app app generate-charts         # write SQC PNG charts to tqm/output/
    flask --app app purge --days 90         # remove old metrics / expired tokens
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path

import click
from flask import Flask

from .extensions import db


def register_cli(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.option("--email", help="Administrator email address")
    @click.option("--name", help="Full name")
    def create_admin(email, name):
        """Create (or promote) an administrator account securely."""
        from .models import User
        from .security import valid_email, validate_password
        from .services.core import log_action
        from .utils import normalize_email, utcnow

        email = normalize_email(email or click.prompt("Admin email"))
        if not valid_email(email):
            raise click.ClickException("Invalid email address.")
        user = User.query.filter_by(email=email).first()
        if user:
            if click.confirm(f"{email} exists (role={user.role}). Promote to admin and verify?", default=True):
                user.role = "admin"
                user.email_verified_at = user.email_verified_at or utcnow()
                user.is_active_account = True
                log_action("admin_promoted_cli", "user", user.id, user_id=user.id)
                db.session.commit()
                click.secho(f"✔ {email} is now an administrator.", fg="green")
            return
        name = name or click.prompt("Full name", default="QuizMaster Admin")
        password = os.environ.get("QM_ADMIN_PASSWORD") or getpass.getpass("Password (input hidden): ")
        if not os.environ.get("QM_ADMIN_PASSWORD"):
            if password != getpass.getpass("Confirm password: "):
                raise click.ClickException("Passwords do not match.")
        problems = validate_password(password, email, name)
        if problems:
            raise click.ClickException(" ".join(problems))
        user = User(full_name=name, email=email, role="admin", email_verified_at=utcnow(), terms_accepted_at=utcnow())
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        log_action("admin_created_cli", "user", user.id, user_id=user.id)
        db.session.commit()
        click.secho(f"✔ Administrator {email} created. Sign in at /auth/admin", fg="green")

    @app.cli.command("seed")
    @click.option("--force", is_flag=True, help="Add sample content even if quizzes already exist")
    def seed_cmd(force):
        """Insert categories, sample quizzes and TQM baseline records."""
        from .seed import seed_all
        report = seed_all(force=force)
        click.secho(f"✔ Seed complete: {report}", fg="green")

    @app.cli.command("backup")
    def backup_cmd():
        """Create a SQLite backup in instance/backups."""
        from .services.backup import create_backup
        click.secho(f"✔ Backup written to {create_backup('cli')}", fg="green")

    @app.cli.command("restore-backup")
    @click.argument("file", type=click.Path(exists=True, dir_okay=False))
    def restore_cmd(file):
        """Restore the database from a backup file (stop the web server first)."""
        from .services.backup import restore_backup
        if not click.confirm("This replaces the current database (a pre-restore backup is made first). Continue?"):
            return
        restore_backup(Path(file))
        click.secho("✔ Database restored. Restart the application.", fg="green")

    @app.cli.command("generate-charts")
    @click.option("--out", default="tqm/output", help="Output directory")
    def charts_cmd(out):
        """Generate Pareto, Fishbone, Control chart, Histogram and FMEA PNGs with Matplotlib."""
        from .models import FMEAItem, QuizAttempt
        from .services import charts
        from .services.quality import control_chart, fishbone_data, pareto_data
        path = Path(out)
        path.mkdir(parents=True, exist_ok=True)
        files = {
            "pareto.png": charts.pareto_png(pareto_data()),
            "fishbone.png": charts.fishbone_png(fishbone_data()),
            "control_chart.png": charts.control_chart_png(control_chart()),
            "score_histogram.png": charts.histogram_png([a.percentage or 0 for a in QuizAttempt.query.filter(
                QuizAttempt.status.in_(("submitted", "expired"))).all()]),
            "fmea_rpn.png": charts.fmea_png(FMEAItem.query.all()),
        }
        for name, png in files.items():
            (path / name).write_bytes(png)
            click.echo(f"  wrote {path / name}")
        click.secho("✔ Charts generated from the live database.", fg="green")

    @app.cli.command("purge")
    @click.option("--days", default=90, show_default=True)
    def purge_cmd(days):
        """Delete request metrics older than N days and expired OTP/reset tokens."""
        from datetime import timedelta

        from .models import EmailOTP, PasswordResetToken, RequestMetric
        from .utils import utcnow
        cutoff = utcnow() - timedelta(days=days)
        n = RequestMetric.query.filter(RequestMetric.created_at < cutoff).delete()
        n += EmailOTP.query.filter(EmailOTP.expires_at < utcnow()).delete()
        n += PasswordResetToken.query.filter(PasswordResetToken.expires_at < utcnow()).delete()
        db.session.commit()
        click.secho(f"✔ Purged {n} rows.", fg="green")
