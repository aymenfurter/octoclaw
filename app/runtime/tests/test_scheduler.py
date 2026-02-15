"""Tests for the Scheduler module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.runtime.scheduler import (
    MIN_INTERVAL_SECONDS,
    Scheduler,
    ScheduledTask,
    _cron_matches,
    _validate_cron,
)


class TestValidateCron:
    def test_valid_hourly(self) -> None:
        _validate_cron("0 * * * *")

    def test_valid_daily(self) -> None:
        _validate_cron("0 9 * * *")

    def test_invalid_expression(self) -> None:
        with pytest.raises(ValueError, match="Invalid cron"):
            _validate_cron("not-a-cron")

    def test_too_frequent(self) -> None:
        with pytest.raises(ValueError, match="minimum"):
            _validate_cron("*/5 * * * *")

    def test_every_minute_rejected(self) -> None:
        with pytest.raises(ValueError, match="minimum"):
            _validate_cron("* * * * *")


class TestCronMatches:
    def test_matches_correct_time(self) -> None:
        dt = datetime(2025, 6, 15, 9, 0, tzinfo=UTC)
        assert _cron_matches("0 9 * * *", dt)

    def test_no_match(self) -> None:
        dt = datetime(2025, 6, 15, 10, 30, tzinfo=UTC)
        assert not _cron_matches("0 9 * * *", dt)

    def test_invalid_cron(self) -> None:
        dt = datetime(2025, 6, 15, 9, 0, tzinfo=UTC)
        assert not _cron_matches("bad", dt)


class TestScheduler:
    def test_add_cron_task(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = sched.add(description="Daily check", prompt="Do a daily check", cron="0 9 * * *")
        assert task.id
        assert task.cron == "0 9 * * *"
        assert task.enabled

    def test_add_one_shot_task(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = sched.add(description="One-time", prompt="Run once", run_at="2030-01-01T00:00:00")
        assert task.run_at == "2030-01-01T00:00:00"

    def test_add_requires_cron_or_run_at(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        with pytest.raises(ValueError):
            sched.add(description="bad", prompt="no schedule")

    def test_rejects_too_frequent_cron(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        with pytest.raises(ValueError, match="minimum|interval|hour"):
            sched.add(description="spam", prompt="x", cron="* * * * *")

    def test_remove_task(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = sched.add(description="del me", prompt="x", cron="0 * * * *")
        assert sched.remove(task.id)
        assert not sched.remove("nonexistent")

    def test_list_tasks(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        sched.add(description="a", prompt="x", cron="0 9 * * *")
        sched.add(description="b", prompt="y", cron="0 18 * * *")
        assert len(sched.list_tasks()) == 2

    def test_update_task(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = sched.add(description="old", prompt="x", cron="0 9 * * *")
        updated = sched.update(task.id, description="new", enabled=False)
        assert updated is not None
        assert updated.description == "new"
        assert not updated.enabled

    def test_get_task(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = sched.add(description="t", prompt="x", cron="0 9 * * *")
        found = sched.get(task.id)
        assert found is not None
        assert found.description == "t"

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        assert sched.get("nope") is None

    def test_persistence(self, tmp_path: Path) -> None:
        db = tmp_path / "scheduler.json"
        sched1 = Scheduler(path=db)
        sched1.add(description="persist", prompt="x", cron="0 9 * * *")
        sched2 = Scheduler(path=db)
        assert len(sched2.list_tasks()) == 1
        assert sched2.list_tasks()[0].description == "persist"

    def test_update_nonexistent(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        assert sched.update("nope", description="x") is None

    def test_check_due_one_shot_past(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        task = sched.add(description="past", prompt="x", run_at=past)
        due = sched.check_due()
        assert len(due) == 1
        assert due[0].id == task.id
        refreshed = sched.get(task.id)
        assert refreshed is not None
        assert not refreshed.enabled

    def test_check_due_one_shot_future(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        future = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
        sched.add(description="future", prompt="x", run_at=future)
        due = sched.check_due()
        assert len(due) == 0

    def test_check_due_disabled_skipped(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        task = sched.add(description="disabled", prompt="x", run_at=past)
        sched.update(task.id, enabled=False)
        due = sched.check_due()
        assert len(due) == 0

    def test_check_due_cron_min_interval_guard(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        now = datetime.now(UTC)
        task = sched.add(description="cron", prompt="x", cron=f"{now.minute} {now.hour} * * *")
        task.last_run = (now - timedelta(seconds=60)).isoformat()
        sched._store.save()
        due = sched.check_due()
        assert len(due) == 0

    def test_check_due_invalid_run_at_skipped(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = sched.add(description="bad", prompt="x", run_at="2020-01-01T00:00:00")
        task.run_at = "not-a-date"
        sched._store.save()
        due = sched.check_due()
        assert len(due) == 0

    def test_set_notify_callback(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        cb = AsyncMock()
        sched.set_notify_callback(cb)
        assert sched._notify is cb

    @pytest.mark.asyncio
    async def test_send_notification(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        cb = AsyncMock()
        sched.set_notify_callback(cb)
        task = ScheduledTask(id="t1", description="Test", prompt="x")
        await sched._send_notification(task, "result text")
        cb.assert_awaited_once()
        msg = cb.call_args[0][0]
        assert "Test" in msg
        assert "result text" in msg

    @pytest.mark.asyncio
    async def test_send_notification_no_callback(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = ScheduledTask(id="t1", description="Test", prompt="x")
        await sched._send_notification(task, "result")

    @pytest.mark.asyncio
    async def test_send_notification_no_result(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        cb = AsyncMock()
        sched.set_notify_callback(cb)
        task = ScheduledTask(id="t1", description="Test", prompt="x")
        await sched._send_notification(task, None)
        msg = cb.call_args[0][0]
        assert "(no output)" in msg

    def test_update_cron_validates(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = sched.add(description="x", prompt="x", cron="0 9 * * *")
        with pytest.raises(ValueError, match="minimum"):
            sched.update(task.id, cron="* * * * *")

    def test_update_ignores_unknown_fields(self, tmp_path: Path) -> None:
        sched = Scheduler(path=tmp_path / "scheduler.json")
        task = sched.add(description="x", prompt="x", cron="0 9 * * *")
        updated = sched.update(task.id, unknown_field="ignored")
        assert updated is not None

    def test_corrupt_db_loads_empty(self, tmp_path: Path) -> None:
        db = tmp_path / "scheduler.json"
        db.write_text("{not a list}")
        sched = Scheduler(path=db)
        assert len(sched.list_tasks()) == 0
