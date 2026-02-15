"""Media type classification and MIME-type registry."""

from __future__ import annotations

EXTENSION_TO_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}

_IMAGE_TYPES = {v for v in EXTENSION_TO_MIME.values() if v.startswith("image/")}
_AUDIO_TYPES = {v for v in EXTENSION_TO_MIME.values() if v.startswith("audio/")}
_VIDEO_TYPES = {v for v in EXTENSION_TO_MIME.values() if v.startswith("video/")}


def classify(content_type: str) -> str:
    """Return ``'image'``, ``'audio'``, ``'video'``, or ``'file'``."""
    mime = content_type.lower().split(";")[0].strip()
    if mime in _IMAGE_TYPES:
        return "image"
    if mime in _AUDIO_TYPES:
        return "audio"
    if mime in _VIDEO_TYPES:
        return "video"
    return "file"
