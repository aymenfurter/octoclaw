"""Tests for one_shot module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.agent.one_shot import auto_approve, _send_and_wait, _safe_stop


class TestAutoApprove:
    @pytest.mark.asyncio
    async def test_returns_allow(self):
        result = await auto_approve({}, {})
        assert result == {"permissionDecision": "allow"}


class TestSendAndWait:
    @pytest.mark.asyncio
    async def test_captures_final_text(self):
        from copilot.generated.session_events import SessionEventType
        from types import SimpleNamespace

        session = MagicMock()
        captured_handler = {}

        def mock_on(handler):
            captured_handler["fn"] = handler

        session.on = mock_on
        session.send = AsyncMock()
        session.destroy = AsyncMock()

        async def run_send():
            task = asyncio.create_task(_send_and_wait(session, "test prompt", 5))
            await asyncio.sleep(0.01)
            fn = captured_handler["fn"]
            fn(SimpleNamespace(
                type=SessionEventType.ASSISTANT_MESSAGE,
                data=SimpleNamespace(content="response text"),
            ))
            fn(SimpleNamespace(
                type=SessionEventType.SESSION_IDLE,
                data=None,
            ))
            return await task

        result = await run_send()
        assert result == "response text"

    @pytest.mark.asyncio
    async def test_handles_destroy_error(self):
        from copilot.generated.session_events import SessionEventType
        from types import SimpleNamespace

        session = MagicMock()
        captured = {}

        def mock_on(handler):
            captured["fn"] = handler

        session.on = mock_on
        session.send = AsyncMock()
        session.destroy = AsyncMock(side_effect=RuntimeError("destroy fail"))

        async def run():
            task = asyncio.create_task(_send_and_wait(session, "p", 5))
            await asyncio.sleep(0.01)
            fn = captured["fn"]
            fn(SimpleNamespace(
                type=SessionEventType.SESSION_IDLE,
                data=None,
            ))
            return await task

        result = await run()
        assert result is None


class TestSafeStop:
    @pytest.mark.asyncio
    async def test_stops_client(self):
        client = AsyncMock()
        await _safe_stop(client)
        client.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handles_stop_error(self):
        client = AsyncMock()
        client.stop.side_effect = RuntimeError("stop fail")
        await _safe_stop(client)
