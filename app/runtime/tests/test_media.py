"""Tests for the media classify module."""

from __future__ import annotations

from app.runtime.media.classify import EXTENSION_TO_MIME, classify


class TestClassify:
    def test_image_jpeg(self) -> None:
        assert classify("image/jpeg") == "image"

    def test_image_png(self) -> None:
        assert classify("image/png") == "image"

    def test_audio_mp3(self) -> None:
        assert classify("audio/mpeg") == "audio"

    def test_video_mp4(self) -> None:
        assert classify("video/mp4") == "video"

    def test_unknown(self) -> None:
        assert classify("application/pdf") == "file"

    def test_case_insensitive(self) -> None:
        assert classify("IMAGE/JPEG") == "image"

    def test_content_type_with_params(self) -> None:
        assert classify("image/png; charset=utf-8") == "image"

    def test_empty_string(self) -> None:
        assert classify("") == "file"


class TestExtensionMap:
    def test_common_extensions_present(self) -> None:
        for ext in (".jpg", ".png", ".mp3", ".mp4", ".gif"):
            assert ext in EXTENSION_TO_MIME

    def test_jpg_mime(self) -> None:
        assert EXTENSION_TO_MIME[".jpg"] == "image/jpeg"
        assert EXTENSION_TO_MIME[".jpeg"] == "image/jpeg"

    def test_audio_mime(self) -> None:
        assert EXTENSION_TO_MIME[".mp3"] == "audio/mpeg"
