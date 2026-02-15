"""Tests for the MessageProcessor module -- pure functions and utilities."""

from __future__ import annotations

from app.runtime.messaging.message_processor import (
    _channel_activity,
    _channel_activity_plain,
    split_message,
)


class TestSplitMessage:
    def test_short_message(self) -> None:
        chunks = split_message("hello", max_len=100)
        assert chunks == ["hello"]

    def test_exact_length(self) -> None:
        msg = "a" * 100
        assert split_message(msg, max_len=100) == [msg]

    def test_splits_on_newline(self) -> None:
        msg = "line1\nline2\nline3"
        chunks = split_message(msg, max_len=12)
        assert len(chunks) >= 2

    def test_splits_on_space(self) -> None:
        msg = "word " * 30
        chunks = split_message(msg.strip(), max_len=50)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 50

    def test_hard_split(self) -> None:
        msg = "x" * 200
        chunks = split_message(msg, max_len=50)
        assert len(chunks) >= 4

    def test_empty_message(self) -> None:
        assert split_message("", max_len=100) == [""]

    def test_default_max_len(self) -> None:
        short = "Hi"
        assert split_message(short) == [short]


class TestChannelActivity:
    def test_default_activity(self) -> None:
        activity = _channel_activity("Hello", "web")
        assert activity.text == "Hello"
        assert activity.type == "message"

    def test_telegram_strips_markdown(self) -> None:
        activity = _channel_activity("**bold**", "telegram")
        assert "**" not in activity.text
        assert activity.text_format == "plain"

    def test_with_attachments(self) -> None:
        attachments = [{"contentType": "image/png", "contentUrl": "http://example.com/img.png"}]
        activity = _channel_activity("See image", "web", attachments=attachments)
        assert activity.attachments == attachments


class TestChannelActivityPlain:
    def test_plain_activity(self) -> None:
        activity = _channel_activity_plain("# Heading")
        assert activity.text_format == "plain"
        assert "#" not in activity.text
