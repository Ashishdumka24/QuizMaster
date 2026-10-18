"""Small shared helpers: time handling, text normalisation, pagination, redirects."""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from flask import current_app, request

# ---------------------------------------------------------------------------
# Time strategy: every timestamp is stored in the database as *naive UTC*.
# Values are converted to APP_TIMEZONE (default Asia/Kolkata) only for display
# and when interpreting administrator-entered local date/times.
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def app_tz() -> ZoneInfo:
    try:
        return ZoneInfo(current_app.config.get("APP_TIMEZONE", "Asia/Kolkata"))
    except Exception:  # pragma: no cover - invalid tz name
        return ZoneInfo("UTC")


def to_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(app_tz())


def local_input_to_utc(value: str | None) -> datetime | None:
    """Convert a `datetime-local` form value (app timezone) to naive UTC."""
    if not value:
        return None
    try:
        local = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if local.tzinfo is None:
        local = local.replace(tzinfo=app_tz())
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local_input(dt: datetime | None) -> str:
    loc = to_local(dt)
    return loc.strftime("%Y-%m-%dT%H:%M") if loc else ""


def iso_utc(dt: datetime | None) -> str | None:
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if dt else None


def fmt_dt(dt: datetime | None, fmt: str = "%d %b %Y, %I:%M %p") -> str:
    loc = to_local(dt)
    return loc.strftime(fmt) if loc else "—"


def fmt_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def time_ago(dt: datetime | None) -> str:
    if not dt:
        return "never"
    delta = (utcnow() - dt).total_seconds()
    if delta < 60:
        return "just now"
    for unit, size in (("year", 31536000), ("month", 2592000), ("day", 86400), ("hour", 3600), ("minute", 60)):
        if delta >= size:
            n = int(delta // size)
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "just now"


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "item"


def clean_text(value, max_len: int | None = None) -> str:
    text = (value or "").strip() if isinstance(value, str) else ""
    text = text.replace("\x00", "")
    if max_len is not None:
        text = text[:max_len]
    return text


def normalize_answer(value: str | None) -> str:
    """Normalisation used for short-answer / fill-in-the-blank auto-grading."""
    text = unicodedata.normalize("NFKC", value or "").casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,!;:")


def parse_tags(raw: str | None) -> str:
    tags = []
    for t in (raw or "").split(","):
        t = t.strip().lower()[:30]
        if t and t not in tags:
            tags.append(t)
    return ",".join(tags[:10])


def to_int(value, default=None, lo=None, hi=None):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if lo is not None and n < lo:
        return default
    if hi is not None and n > hi:
        return default
    return n


def to_float(value, default=None, lo=None, hi=None):
    try:
        n = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    if math.isnan(n) or math.isinf(n):
        return default
    if lo is not None and n < lo:
        return default
    if hi is not None and n > hi:
        return default
    return n


# ---------------------------------------------------------------------------
# Safe redirects (prevents open-redirect attacks via ?next=)
# ---------------------------------------------------------------------------

def is_safe_url(target: str | None) -> bool:
    if not target or target.startswith("//") or "\\" in target:
        return False
    host = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    return test.scheme in ("http", "https") and host.netloc == test.netloc


class Page:
    """Minimal pagination value object used by list views."""

    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = max(1, math.ceil(total / per_page)) if per_page else 1
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1
        self.next_num = page + 1

    def iter_pages(self, window: int = 2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= 1 or num > self.pages - 1 or abs(num - self.page) <= window:
                if last + 1 != num:
                    yield None
                yield num
                last = num


def paginate(query, page: int | None = None, per_page: int = 15) -> Page:
    page = page or to_int(request.args.get("page"), 1, lo=1) or 1
    total = query.order_by(None).count()
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    return Page(items, page, per_page, total)
