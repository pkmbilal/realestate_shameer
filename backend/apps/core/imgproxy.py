"""Signed imgproxy URLs, so every image is served resized (CLAUDE.md §6)."""

import base64
import hashlib
import hmac

from django.conf import settings


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def imgproxy_url(key: str, width: int, height: int, *, fit: str = "fill") -> str:
    """URL of the stored image `key`, resized to width×height and served as WebP."""
    source = f"s3://{settings.STORAGES['default']['OPTIONS']['bucket_name']}/{key}"
    path = f"/rs:{fit}:{width}:{height}:0/{_b64(source.encode())}.webp"
    signature = hmac.new(
        bytes.fromhex(settings.IMGPROXY_KEY),
        bytes.fromhex(settings.IMGPROXY_SALT) + path.encode(),
        hashlib.sha256,
    ).digest()
    return f"{settings.IMGPROXY_URL.rstrip('/')}/{_b64(signature)}{path}"
