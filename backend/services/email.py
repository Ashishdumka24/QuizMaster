"""Transactional email delivery.

Delivery modes
--------------
* ``smtp``   – real delivery through the SMTP server configured in `.env`
               (Gmail App Password, Brevo, SendGrid SMTP relay, Mailgun, Zoho...).
* ``outbox`` – DEVELOPMENT ONLY. When SMTP is not configured and
               ``MAIL_DEV_OUTBOX`` is enabled, messages are written to
               ``instance/outbox`` and can be previewed at ``/dev/outbox``.
               This mode is forcibly disabled when ``APP_ENV=production``.

If neither mode is available an :class:`EmailDeliveryError` is raised and the
caller must report the failure – a failed delivery is never shown as success.
"""
from __future__ import annotations

import json
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from pathlib import Path

from flask import current_app, has_request_context, render_template, request

from ..utils import slugify, utcnow


class EmailDeliveryError(Exception):
    pass


def smtp_configured() -> bool:
    cfg = current_app.config
    return bool(cfg.get("MAIL_SERVER") and (cfg.get("MAIL_DEFAULT_SENDER") or cfg.get("MAIL_USERNAME")))


def outbox_enabled() -> bool:
    cfg = current_app.config
    return bool(cfg.get("MAIL_DEV_OUTBOX")) and cfg.get("APP_ENV") != "production" and not smtp_configured()


def delivery_mode() -> str:
    if smtp_configured():
        return "smtp"
    if outbox_enabled():
        return "outbox"
    return "unavailable"


def outbox_dir() -> Path:
    path = Path(current_app.config["INSTANCE_DIR"]) / "outbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _html_to_text(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</h\d>|</tr>|</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def send_email(to: str, subject: str, template: str, **context) -> str:
    """Render ``templates/emails/<template>.html`` and deliver it.

    Returns the delivery mode used (``smtp`` or ``outbox``) or raises
    :class:`EmailDeliveryError`.
    """
    cfg = current_app.config
    context.setdefault("app_name", cfg["APP_NAME"])
    if cfg.get("APP_BASE_URL_EXPLICIT") or not has_request_context():
        context.setdefault("base_url", cfg["APP_BASE_URL"])
    else:
        context.setdefault("base_url", request.url_root.rstrip("/"))
    context.setdefault("year", utcnow().year)
    html = render_template(f"emails/{template}.html", subject=subject, **context)
    text = _html_to_text(html)
    mode = delivery_mode()

    if mode == "smtp":
        sender = cfg.get("MAIL_DEFAULT_SENDER") or cfg.get("MAIL_USERNAME")
        name, addr = parseaddr(sender)
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((name or cfg["APP_NAME"], addr))
        msg["To"] = to
        msg["Message-ID"] = make_msgid(domain=(addr.split("@")[-1] if "@" in addr else None))
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        try:
            context_ssl = ssl.create_default_context()
            if cfg.get("MAIL_USE_SSL"):
                server = smtplib.SMTP_SSL(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=cfg["MAIL_TIMEOUT"],
                                          context=context_ssl)
            else:
                server = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=cfg["MAIL_TIMEOUT"])
            with server:
                server.ehlo()
                if cfg.get("MAIL_USE_TLS") and not cfg.get("MAIL_USE_SSL"):
                    server.starttls(context=context_ssl)
                    server.ehlo()
                if cfg.get("MAIL_USERNAME"):
                    server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
                server.send_message(msg)
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            current_app.logger.error("SMTP delivery to %s failed: %s", to, exc.__class__.__name__)
            raise EmailDeliveryError("We could not send the email right now. Please try again shortly.") from exc
        return "smtp"

    if mode == "outbox":
        stamp = utcnow().strftime("%Y%m%d-%H%M%S-%f")
        base = f"{stamp}-{slugify(subject)[:40]}"
        folder = outbox_dir()
        (folder / f"{base}.html").write_text(html, encoding="utf-8")
        (folder / f"{base}.json").write_text(json.dumps({
            "to": to, "subject": subject, "created_at": utcnow().isoformat() + "Z", "file": f"{base}.html",
        }), encoding="utf-8")
        current_app.logger.warning("[DEV OUTBOX] Email to %s saved as %s (SMTP not configured).", to, base)
        return "outbox"

    raise EmailDeliveryError(
        "Email delivery is not configured on this server. Please contact the administrator."
    )


def list_outbox(limit: int = 50) -> list[dict]:
    items = []
    for meta in sorted(outbox_dir().glob("*.json"), reverse=True)[:limit]:
        try:
            items.append(json.loads(meta.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return items
