"""Tests for MemoryFormation class."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.state.memory import MemoryFormation, _ChatEntry, get_memory, _reset_memory


class TestChatEntry:
    def test_fields(self) -> None:
        e = _ChatEntry(role="user", text="hello", timestamp="2025-01-01 00:00:00 UTC")
        assert e.role == "user"
        assert e.text == "hello"
        assert e.timestamp == "2025-01-01 00:00:00 UTC"


class TestMemoryFormationRecord:
    def test_record_appends(self) -> None:
        m = MemoryFormation()
        m.record("user", "hello")
        assert len(m._log) == 1
        assert m._log[0].role == "user"
        assert m._log[0].text == "hello"

    def test_record_ignores_empty(self) -> None:
        m = MemoryFormation()
        m.record("user", "")
        assert len(m._log) == 0

    def test_record_multiple(self) -> None:
        m = MemoryFormation()
        m.record("user", "hello")
        m.record("assistant", "hi there")
        m.record("user", "how are you")
        assert len(m._log) == 3

    def test_record_sets_timestamp(self) -> None:
        m = MemoryFormation()
        m.record("user", "hello")
        assert "UTC" in m._log[0].timestamp


class TestMemoryFormationStatus:
    def test_initial_status(self) -> None:
        m = MemoryFormation()
        s = m.get_status()
        assert s["buffered_turns"] == 0
        assert s["timer_active"] is False
        assert s["forming_now"] is False
        assert s["formation_count"] == 0
        assert s["last_formed_at"] is None
        assert s["last_error"] is None

    def test_status_after_record(self) -> None:
        m = MemoryFormation()
        m.record("user", "hello")
        s = m.get_status()
        assert s["buffered_turns"] == 1


class TestFormatTranscript:
    def test_basic(self) -> None:
        entries = [
            _ChatEntry(role="user", text="Hello", timestamp="2025-01-01 12:00:00 UTC"),
            _ChatEntry(role="assistant", text="Hi!", timestamp="2025-01-01 12:00:01 UTC"),
        ]
        result = MemoryFormation._format_transcript(entries)
        assert "User: Hello" in result
        assert "Assistant: Hi!" in result
        assert "2025-01-01 12:00:00 UTC" in result


class TestOnMessages:
    def test_on_user_message(self) -> None:
        m = MemoryFormation()
        m.on_user_message = m.record.__get__(m)  # type: ignore[attr-defined]

    def test_on_assistant_message(self) -> None:
        m = MemoryFormation()
        m.on_assistant_message = m.record.__get__(m)  # type: ignore[attr-defined]


class TestProcessProactiveReaction:
    def test_no_file(self, tmp_path: Path) -> None:
        with patch("app.runtime.state.memory.cfg") as mock_cfg:
            mock_cfg.data_dir = tmp_path
            MemoryFormation._process_proactive_reaction()

    def test_valid_positive(self, tmp_path: Path) -> None:
        reaction_path = tmp_path / "proactive_reaction.json"
        reaction_path.write_text(json.dumps({"reaction": "positive", "detail": "liked it"}))
        mock_store = MagicMock()
        mock_store.enabled = True
        mock_store.history = []
        mock_store.preferences = MagicMock()
        mock_store.preferences.avoided_topics = []
        with patch("app.runtime.state.memory.cfg") as mock_cfg, \
             patch("app.runtime.state.memory.get_proactive_store", return_value=mock_store):
            mock_cfg.data_dir = tmp_path
            MemoryFormation._process_proactive_reaction()
        mock_store.mark_latest_reaction.assert_called_once_with("positive", "liked it")
        assert not reaction_path.exists()

    def test_valid_negative_adds_topic(self, tmp_path: Path) -> None:
        reaction_path = tmp_path / "proactive_reaction.json"
        reaction_path.write_text(json.dumps({"reaction": "negative", "detail": "meetings"}))
        mock_store = MagicMock()
        mock_store.enabled = True
        mock_store.history = []
        mock_store.preferences = MagicMock()
        mock_store.preferences.avoided_topics = []
        with patch("app.runtime.state.memory.cfg") as mock_cfg, \
             patch("app.runtime.state.memory.get_proactive_store", return_value=mock_store):
            mock_cfg.data_dir = tmp_path
            MemoryFormation._process_proactive_reaction()
        mock_store.update_preferences.assert_called_once()
        avoided = mock_store.update_preferences.call_args[1]["avoided_topics"]
        assert "meetings" in avoided

    def test_invalid_reaction_value(self, tmp_path: Path) -> None:
        reaction_path = tmp_path / "proactive_reaction.json"
        reaction_path.write_text(json.dumps({"reaction": "maybe", "detail": "idk"}))
        mock_store = MagicMock()
        with patch("app.runtime.state.memory.cfg") as mock_cfg, \
             patch("app.runtime.state.memory.get_proactive_store", return_value=mock_store):
            mock_cfg.data_dir = tmp_path
            MemoryFormation._process_proactive_reaction()
        mock_store.mark_latest_reaction.assert_not_called()

    def test_corrupt_json(self, tmp_path: Path) -> None:
        reaction_path = tmp_path / "proactive_reaction.json"
        reaction_path.write_text("not json")
        with patch("app.runtime.state.memory.cfg") as mock_cfg:
            mock_cfg.data_dir = tmp_path
            MemoryFormation._process_proactive_reaction()
        assert not reaction_path.exists()


class TestProcessProactiveFollowup:
    @pytest.mark.asyncio
    async def test_no_file(self, tmp_path: Path) -> None:
        m = MemoryFormation()
        with patch("app.runtime.state.memory.cfg") as mock_cfg:
            mock_cfg.data_dir = tmp_path
            await m._process_proactive_followup()

    @pytest.mark.asyncio
    async def test_valid_followup(self, tmp_path: Path) -> None:
        followup_path = tmp_path / "proactive_followup.json"
        followup_path.write_text(json.dumps({
            "message": "Hey, check this out",
            "deliver_at": "2025-01-01T14:00:00",
            "context": "user mentioned interest",
        }))
        mock_store = MagicMock()
        mock_store.enabled = True
        mock_store.preferences = MagicMock()
        mock_store.preferences.max_daily = 10
        mock_store.preferences.min_gap_hours = 1
        mock_store.messages_sent_today.return_value = 0
        mock_store.hours_since_last_sent.return_value = 5.0
        m = MemoryFormation()
        with patch("app.runtime.state.memory.cfg") as mock_cfg, \
             patch("app.runtime.state.memory.get_proactive_store", return_value=mock_store):
            mock_cfg.data_dir = tmp_path
            await m._process_proactive_followup()
        mock_store.schedule_followup.assert_called_once()
        assert m._last_proactive_scheduled is True
        assert not followup_path.exists()

    @pytest.mark.asyncio
    async def test_daily_limit_reached(self, tmp_path: Path) -> None:
        followup_path = tmp_path / "proactive_followup.json"
        followup_path.write_text(json.dumps({
            "message": "Hey", "deliver_at": "2025-01-01T14:00:00", "context": ""
        }))
        mock_store = MagicMock()
        mock_store.preferences = MagicMock()
        mock_store.preferences.max_daily = 3
        mock_store.preferences.min_gap_hours = 1
        mock_store.messages_sent_today.return_value = 5
        mock_store.hours_since_last_sent.return_value = 10.0
        m = MemoryFormation()
        with patch("app.runtime.state.memory.cfg") as mock_cfg, \
             patch("app.runtime.state.memory.get_proactive_store", return_value=mock_store):
            mock_cfg.data_dir = tmp_path
            await m._process_proactive_followup()
        mock_store.schedule_followup.assert_not_called()

    @pytest.mark.asyncio
    async def test_gap_too_short(self, tmp_path: Path) -> None:
        followup_path = tmp_path / "proactive_followup.json"
        followup_path.write_text(json.dumps({
            "message": "Hey", "deliver_at": "2025-01-01T14:00:00", "context": ""
        }))
        mock_store = MagicMock()
        mock_store.preferences = MagicMock()
        mock_store.preferences.max_daily = 10
        mock_store.preferences.min_gap_hours = 4
        mock_store.messages_sent_today.return_value = 0
        mock_store.hours_since_last_sent.return_value = 1.0
        m = MemoryFormation()
        with patch("app.runtime.state.memory.cfg") as mock_cfg, \
             patch("app.runtime.state.memory.get_proactive_store", return_value=mock_store):
            mock_cfg.data_dir = tmp_path
            await m._process_proactive_followup()
        mock_store.schedule_followup.assert_not_called()

    @pytest.mark.asyncio
    async def test_incomplete_data(self, tmp_path: Path) -> None:
        followup_path = tmp_path / "proactive_followup.json"
        followup_path.write_text(json.dumps({"message": "", "deliver_at": ""}))
        mock_store = MagicMock()
        m = MemoryFormation()
        with patch("app.runtime.state.memory.cfg") as mock_cfg, \
             patch("app.runtime.state.memory.get_proactive_store", return_value=mock_store):
            mock_cfg.data_dir = tmp_path
            await m._process_proactive_followup()
        mock_store.schedule_followup.assert_not_called()


class TestForceForm:
    @pytest.mark.asyncio
    async def test_no_turns(self) -> None:
        m = MemoryFormation()
        result = await m.force_form()
        assert result["status"] == "no_turns"

    @pytest.mark.asyncio
    async def test_already_running(self) -> None:
        m = MemoryFormation()
        m.record("user", "hello")
        m._forming = True
        result = await m.force_form()
        assert result["status"] == "already_running"

    @pytest.mark.asyncio
    async def test_triggers_formation(self, tmp_path: Path) -> None:
        m = MemoryFormation()
        m.record("user", "hello")
        m.record("assistant", "hi there")
        with patch("app.runtime.state.memory.cfg") as mock_cfg, \
             patch("app.runtime.state.memory.get_proactive_store") as mock_ps:
            mock_cfg.memory_model = "test-model"
            mock_cfg.memory_idle_minutes = 5
            mock_cfg.memory_daily_dir = tmp_path / "daily"
            mock_cfg.memory_topics_dir = tmp_path / "topics"
            mock_cfg.data_dir = tmp_path
            mock_cfg.memory_dir = tmp_path
            mock_ps.return_value.enabled = False
            with patch("app.runtime.state.memory.MemoryFormation._form_memory", new_callable=AsyncMock) as mock_form:
                result = await m.force_form()
        assert result["status"] == "ok"
        mock_form.assert_awaited_once()


class TestGetMemorySingleton:
    def test_returns_same_instance(self) -> None:
        _reset_memory()
        m1 = get_memory()
        m2 = get_memory()
        assert m1 is m2
        _reset_memory()

    def test_reset_creates_new(self) -> None:
        _reset_memory()
        m1 = get_memory()
        _reset_memory()
        m2 = get_memory()
        assert m1 is not m2
        _reset_memory()


class TestGatherSessionTiming:
    def test_no_sessions(self) -> None:
        with patch("app.runtime.state.session_store.SessionStore") as MockStore:
            MockStore.return_value.list_sessions.return_value = []
            result = MemoryFormation._gather_session_timing()
        assert "No previous sessions" in result

    def test_with_sessions(self) -> None:
        sessions = [
            {"started_at": "2025-01-01T10:00:00+00:00", "message_count": 5, "channel": "web"},
            {"started_at": "2025-01-01T08:00:00+00:00", "message_count": 3, "channel": "telegram"},
        ]
        with patch("app.runtime.state.session_store.SessionStore") as MockStore:
            MockStore.return_value.list_sessions.return_value = sessions
            result = MemoryFormation._gather_session_timing()
        assert "Total sessions recorded: 2" in result
        assert "web" in result

    def test_with_many_sessions(self) -> None:
        sessions = [
            {"started_at": f"2025-01-{10-i:02d}T{10+i}:00:00+00:00", "message_count": i, "channel": "web"}
            for i in range(5)
        ]
        with patch("app.runtime.state.session_store.SessionStore") as MockStore:
            MockStore.return_value.list_sessions.return_value = sessions
            result = MemoryFormation._gather_session_timing()
        assert "Average gap" in result
        assert "active between" in result
