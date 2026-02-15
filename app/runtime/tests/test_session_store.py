"""Tests for the SessionStore."""

from __future__ import annotations

from pathlib import Path

from app.runtime.state.session_store import SessionStore


class TestSessionStore:
    def test_start_and_record(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        store.start_session("s1", model="gpt-4.1")
        store.record("user", "hello")
        store.record("assistant", "hi there")

        data = store.get_session("s1")
        assert data is not None
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"

    def test_record_without_session_is_noop(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        store.record("user", "hello")
        assert store.current_session_id == ""

    def test_delete_session(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        store.start_session("s2", model="test")
        store.record("user", "x")
        assert store.delete_session("s2")
        assert store.get_session("s2") is None

    def test_clear_all(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        store.start_session("a")
        store.record("user", "x")
        store.start_session("b")
        store.record("user", "y")
        count = store.clear_all()
        assert count == 2
        assert store.list_sessions() == []

    def test_list_sessions(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        store.start_session("s1", model="a")
        store.record("user", "hello")
        store.start_session("s2", model="b")
        store.record("user", "world")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_stats(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        store.start_session("s1")
        store.record("user", "msg1")
        store.record("assistant", "msg2")
        stats = store.get_session_stats()
        assert stats["total_sessions"] == 1
        assert stats["total_messages"] == 2

    def test_archival_policy(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        assert store.get_archival_policy() == "7d"
        store.set_archival_policy("never")
        assert store.get_archival_policy() == "never"

    def test_invalid_archival_policy(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        import pytest

        with pytest.raises(ValueError):
            store.set_archival_policy("invalid")

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        assert not store.delete_session("nonexistent")

    def test_empty_sessions_not_persisted(self, tmp_path: Path) -> None:
        store = SessionStore(directory=tmp_path / "sessions")
        store.start_session("empty-1", model="gpt-4.1")
        # No messages recorded -- file should not exist
        assert not (tmp_path / "sessions" / "empty-1.json").exists()
        assert store.list_sessions() == []

    def test_empty_sessions_purged_on_init(self, tmp_path: Path) -> None:
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        # Manually create an empty session file (legacy)
        import json
        (sessions_dir / "stale.json").write_text(
            json.dumps({"id": "stale", "messages": [], "model": "x",
                        "created_at": 0, "updated_at": 0, "title": ""})
        )
        store = SessionStore(directory=sessions_dir)
        assert not (sessions_dir / "stale.json").exists()
        assert store.list_sessions() == []
