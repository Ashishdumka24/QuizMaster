"""Safe image uploads (profile photos and question images).

The file extension and browser-supplied MIME type are ignored. Pillow decodes
the bytes; only real JPEG/PNG/WEBP/GIF images within size and pixel limits are
accepted. The image is re-encoded to WebP (stripping metadata and any embedded
payload) and saved under a random filename outside the static folder.
"""
from __future__ import annotations

import io
import secrets
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
MAX_PIXELS = 25_000_000  # guards against decompression bombs


class UploadError(Exception):
    pass


def upload_dir(kind: str) -> Path:
    if kind not in ("avatars", "questions"):
        raise ValueError("unknown upload kind")
    path = Path(current_app.config["INSTANCE_DIR"]) / "uploads" / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_image(file_storage, kind: str, max_bytes: int, max_side: int, square: bool = False) -> str:
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise UploadError("Please choose an image file.")
    data = file_storage.read(max_bytes + 1)
    if not data:
        raise UploadError("The selected file is empty.")
    if len(data) > max_bytes:
        raise UploadError(f"Image is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.")

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise UploadError("Unsupported image format. Use JPG, PNG, WEBP or GIF.")
        img = Image.open(io.BytesIO(data))
        img.load()
    except UploadError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, ValueError):
        raise UploadError("This file is not a valid image.") from None

    if img.width * img.height > MAX_PIXELS:
        raise UploadError("Image dimensions are too large.")
    img = ImageOps.exif_transpose(img)
    if getattr(img, "is_animated", False):
        img.seek(0)
    img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
    if square:
        img = ImageOps.fit(img, (max_side, max_side), Image.Resampling.LANCZOS)
    else:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    name = f"{secrets.token_hex(16)}.webp"
    dest = upload_dir(kind) / name
    img.save(dest, "WEBP", quality=86, method=4)
    return name


def delete_upload(kind: str, filename: str | None) -> None:
    if not filename:
        return
    safe = Path(filename).name  # strip any path component
    if safe != filename or not safe.endswith(".webp"):
        return
    try:
        (upload_dir(kind) / safe).unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Could not delete upload %s/%s", kind, safe)
