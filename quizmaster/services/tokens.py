"""Email OTP verification and password-reset tokens.

* Codes/tokens come from the `secrets` CSPRNG.
* Only an HMAC-SHA256 digest (keyed with TOKEN_PEPPER/SECRET_KEY) is stored.
* OTPs expire (OTP_TTL_MINUTES), are single use, allow OTP_MAX_ATTEMPTS
  guesses, and issuing a new code invalidates all older codes.
* Resends are throttled by a cooldown and an hourly cap.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from flask import current_app, url_for

from ..extensions import db
from ..models import EmailOTP, PasswordResetToken, User
from ..utils import utcnow
from .email import EmailDeliveryError, send_email


class OTPError(Exception):
    def __init__(self, message: str, code: str = "otp_error", retry_after: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retry_after = retry_after


def _pepper() -> bytes:
    cfg = current_app.config
    return (cfg.get("TOKEN_PEPPER") or cfg["SECRET_KEY"]).encode()


def token_hash(value: str) -> str:
    return hmac.new(_pepper(), value.encode(), hashlib.sha256).hexdigest()


def _active_otps(user: User, purpose: str = "verify"):
    return EmailOTP.query.filter(
        EmailOTP.user_id == user.id, EmailOTP.purpose == purpose,
        EmailOTP.consumed_at.is_(None), EmailOTP.invalidated_at.is_(None),
    )


def otp_send_wait_seconds(user: User, purpose: str = "verify") -> int:
    """Seconds until another code may be sent (0 = allowed now)."""
    cfg = current_app.config
    now = utcnow()
    last = EmailOTP.query.filter_by(user_id=user.id, purpose=purpose).order_by(EmailOTP.created_at.desc()).first()
    wait = 0
    if last:
        elapsed = (now - last.created_at).total_seconds()
        wait = max(0, int(cfg["OTP_RESEND_COOLDOWN_SECONDS"] - elapsed))
    hour_count = EmailOTP.query.filter(EmailOTP.user_id == user.id, EmailOTP.purpose == purpose,
                                       EmailOTP.created_at > now - timedelta(hours=1)).count()
    if hour_count >= cfg["OTP_MAX_SENDS_PER_HOUR"]:
        oldest = EmailOTP.query.filter(EmailOTP.user_id == user.id, EmailOTP.purpose == purpose,
                                       EmailOTP.created_at > now - timedelta(hours=1)) \
            .order_by(EmailOTP.created_at.asc()).first()
        wait = max(wait, int(3600 - (now - oldest.created_at).total_seconds()) + 1)
    return wait


def issue_verification_otp(user: User, enforce_limits: bool = True) -> str:
    """Create, store (hashed) and email a new verification code.

    Returns the delivery mode. Raises OTPError on throttling or delivery failure.
    The database is committed by this function.
    """
    cfg = current_app.config
    if enforce_limits:
        wait = otp_send_wait_seconds(user)
        if wait > 0:
            raise OTPError(f"Please wait {wait} seconds before requesting another code.", "throttled", wait)

    now = utcnow()
    for old in _active_otps(user).all():
        old.invalidated_at = now

    code = f"{secrets.randbelow(10 ** cfg['OTP_LENGTH']):0{cfg['OTP_LENGTH']}d}"
    otp = EmailOTP(user_id=user.id, purpose="verify", code_hash=token_hash(f"verify:{user.id}:{code}"),
                   expires_at=now + timedelta(minutes=cfg["OTP_TTL_MINUTES"]), created_at=now)
    db.session.add(otp)
    db.session.commit()

    try:
        mode = send_email(user.email, f"{code} is your QuizMaster verification code", "verify_otp",
                          user=user, code=code, ttl=cfg["OTP_TTL_MINUTES"])
    except EmailDeliveryError as exc:
        otp.invalidated_at = utcnow()
        db.session.commit()
        raise OTPError(str(exc), "delivery_failed") from exc
    return mode


def verify_otp(user: User, code: str) -> None:
    """Validate a submitted code. Marks the email as verified on success."""
    cfg = current_app.config
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != cfg["OTP_LENGTH"]:
        raise OTPError(f"Enter the {cfg['OTP_LENGTH']}-digit code from your email.", "invalid_format")

    otp = _active_otps(user).order_by(EmailOTP.created_at.desc()).first()
    now = utcnow()
    if otp is None:
        raise OTPError("There is no active code for this account. Request a new code.", "no_code")
    if otp.expires_at <= now:
        otp.invalidated_at = now
        db.session.commit()
        raise OTPError("This code has expired. Request a new code to continue.", "expired")
    if otp.attempts >= cfg["OTP_MAX_ATTEMPTS"]:
        otp.invalidated_at = now
        db.session.commit()
        raise OTPError("Too many incorrect attempts. Request a new code.", "locked")

    otp.attempts += 1
    expected = token_hash(f"verify:{user.id}:{code}")
    if not hmac.compare_digest(expected, otp.code_hash):
        remaining = cfg["OTP_MAX_ATTEMPTS"] - otp.attempts
        if remaining <= 0:
            otp.invalidated_at = now
        db.session.commit()
        if remaining <= 0:
            raise OTPError("Too many incorrect attempts. Request a new code.", "locked")
        raise OTPError(f"That code is incorrect. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
                       "incorrect")

    otp.consumed_at = now
    user.email_verified_at = now
    db.session.commit()


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def issue_reset_token(user: User, ip: str | None = None) -> str:
    """Create a reset token and email the link. Returns delivery mode."""
    cfg = current_app.config
    now = utcnow()
    PasswordResetToken.query.filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)) \
        .update({PasswordResetToken.used_at: now}, synchronize_session=False)
    raw = secrets.token_urlsafe(32)
    db.session.add(PasswordResetToken(user_id=user.id, token_hash=token_hash(f"reset:{raw}"),
                                      expires_at=now + timedelta(minutes=cfg["RESET_TOKEN_TTL_MINUTES"]),
                                      request_ip=ip))
    db.session.commit()
    link = cfg["APP_BASE_URL"] + url_for("auth.reset_password", token=raw)
    return send_email(user.email, "Reset your QuizMaster password", "reset_password", user=user, link=link,
                      ttl=cfg["RESET_TOKEN_TTL_MINUTES"])


def find_reset_token(raw: str) -> PasswordResetToken | None:
    if not raw or len(raw) > 200:
        return None
    rec = PasswordResetToken.query.filter_by(token_hash=token_hash(f"reset:{raw}")).first()
    if rec is None or rec.used_at is not None or rec.expires_at <= utcnow():
        return None
    return rec
