"""Tests for the ProactiveStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.runtime.state.proactive import PendingMessage, ProactiveStore


class TestProactiveStore:
    def test_initial_state(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        assert store.pending is None
        assert store.history == []
        assert not store.enabled

    def test_enable_disable(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        store.enabled = True
        assert store.enabled
        store.enabled = False
        assert not store.enabled

    def test_schedule_followup(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        deliver = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
        msg = store.schedule_followup("Hello!", deliver_at=deliver, context="test")
        assert msg.message == "Hello!"
        assert store.pending is not None
        assert store.pending.id == msg.id

    def test_clear_pending(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        deliver = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        store.schedule_followup("Hi", deliver_at=deliver)
        cleared = store.clear_pending()
        assert cleared is not None
        assert store.pending is None

    def test_clear_pending_when_empty(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        assert store.clear_pending() is None

    def test_record_sent(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        sent = store.record_sent("Hey there", context="greeting")
        assert sent.message == "Hey there"
        assert len(store.history) == 1

    def test_history_cap(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        for i in range(110):
            store.record_sent(f"msg {i}")
        assert len(store.history) == 100

    def test_update_reaction(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        sent = store.record_sent("Test")
        ok = store.update_reaction(sent.id, "positive", "liked it")
        assert ok
        assert store.history[-1].reaction == "positive"

    def test_update_reaction_not_found(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        assert not store.update_reaction("nonexistent", "positive")

    def test_mark_latest_reaction(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        store.record_sent("A")
        store.record_sent("B")
        ok = store.mark_latest_reaction("negative", "too early")
        assert ok
        assert store.history[-1].reaction == "negative"

    def test_mark_latest_reaction_empty(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        assert not store.mark_latest_reaction("positive")

    def test_preferences(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        prefs = store.preferences
        assert prefs.min_gap_hours == 4
        assert prefs.max_daily == 3

    def test_update_preferences(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        store.update_preferences(min_gap_hours=6, max_daily=5)
        prefs = store.preferences
        assert prefs.min_gap_hours == 6
        assert prefs.max_daily == 5

    def test_messages_sent_today(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        store.record_sent("A")
        store.record_sent("B")
        assert store.messages_sent_today() == 2

    def test_hours_since_last_sent(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        assert store.hours_since_last_sent() is None
        store.record_sent("A")
        hours = store.hours_since_last_sent()
        assert hours is not None
        assert hours < 0.1

    def test_is_due_no_pending(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        assert not store.is_due()

    def test_is_due_future(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        future = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
        store.schedule_followup("Later", deliver_at=future)
        assert not store.is_due()

    def test_is_due_past(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        store.schedule_followup("Now", deliver_at=past)
        assert store.is_due()

    def test_get_full_state(self, tmp_path: Path) -> None:
        store = ProactiveStore(path=tmp_path / "proactive.json")
        store.record_sent("X")
        state = store.get_full_state()
        assert "enabled" in state
        assert "history" in state
        assert state["messages_sent_today"] == 1

    def test_persistence(self, tmp_path: Path) -> None:
        db = tmp_path / "proactive.json"
        s1 = ProactiveStore(path=db)
        s1.record_sent("Persistent")
        s2 = ProactiveStore(path=db)
        assert len(s2.history) == 1
        assert s2.history[0].message == "Persistent"
