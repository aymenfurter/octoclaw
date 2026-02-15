"""Tests for the MemoryFormation module -- record, status, transcript."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.runtime.state.memory import MemoryFormation, _ChatEntry


class TestChatEntry:
    def test_creation(self) -> None:
        e = _ChatEntry(role="user", text="hello", timestamp="2025-01-01 00:00:00 UTC")
        assert e.role == "user"
        assert e.text == "hello"
        assert e.timestamp == "2025-01-01 00:00:00 UTC"


class TestMemoryFormation:
    def test_initial_status(self) -> None:
        mem = MemoryFormation()
        status = mem.get_status()
        assert status["buffered_turns"] == 0
        assert status["timer_active"] is False
        assert status["forming_now"] is False
        assert status["formation_count"] == 0
        assert status["last_formed_at"] is None
        assert status["last_error"] is None

    def test_record_adds_to_log(self) -> None:
        mem = MemoryFormation()
        mem.record("user", "hello")
        assert mem.get_status()["buffered_turns"] == 1
        mem.record("assistant", "hi back")
        assert mem.get_status()["buffered_turns"] == 2

    def test_record_empty_text_ignored(self) -> None:
        mem = MemoryFormation()
        mem.record("user", "")
        assert mem.get_status()["buffered_turns"] == 0

    def test_record_none_text_ignored(self) -> None:
        mem = MemoryFormation()
        mem.record("user", "")
        assert mem.get_status()["buffered_turns"] == 0

    def test_format_transcript(self) -> None:
        entries = [
            _ChatEntry(role="user", text="hello", timestamp="2025-01-01 10:00:00 UTC"),
            _ChatEntry(role="assistant", text="hi", timestamp="2025-01-01 10:00:01 UTC"),
        ]
        transcript = MemoryFormation._format_transcript(entries)
        assert "User: hello" in transcript
        assert "Assistant: hi" in transcript
        assert "10:00:00" in transcript

    def test_format_transcript_empty(self) -> None:
        assert MemoryFormation._format_transcript([]) == ""

    def test_multiple_records_increment(self) -> None:
        mem = MemoryFormation()
        for i in range(5):
            mem.record("user", f"msg {i}")
        assert mem.get_status()["buffered_turns"] == 5

    def test_status_fields(self) -> None:
        mem = MemoryFormation()
        status = mem.get_status()
        expected_keys = {
            "buffered_turns", "timer_active", "forming_now",
            "idle_minutes", "formation_count", "last_formed_at",
            "last_turns_processed", "last_error", "last_proactive_scheduled",
        }
        assert expected_keys == set(status.keys())
