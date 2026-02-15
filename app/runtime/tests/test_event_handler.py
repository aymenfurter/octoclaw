"""Tests for the agent EventHandler dispatch logic."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.runtime.agent.event_handler import EventHandler, _extract_tool_name


def _make_event(etype, **data_attrs):
    data = SimpleNamespace(**data_attrs)
    return SimpleNamespace(type=etype, data=data)


class TestExtractToolName:
    def test_uses_tool_name(self):
        data = SimpleNamespace(tool_name="my_tool", name=None)
        assert _extract_tool_name(data) == "my_tool"

    def test_uses_mcp_tool_name(self):
        data = SimpleNamespace(tool_name=None, mcp_tool_name="mcp_t", name=None)
        assert _extract_tool_name(data) == "mcp_t"

    def test_uses_name(self):
        data = SimpleNamespace(tool_name=None, name="fallback_name")
        assert _extract_tool_name(data) == "fallback_name"

    def test_returns_fallback(self):
        data = SimpleNamespace(tool_name=None, name=None)
        assert _extract_tool_name(data) == "unknown"

    def test_custom_fallback(self):
        data = SimpleNamespace(tool_name=None, name=None)
        assert _extract_tool_name(data, "custom") == "custom"


class TestEventHandler:
    def test_init_defaults(self):
        h = EventHandler()
        assert h.final_text is None
        assert h.error is None
        assert not h.done.is_set()

    def test_assistant_message_delta(self):
        deltas = []
        h = EventHandler(on_delta=lambda d: deltas.append(d))
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(SessionEventType.ASSISTANT_MESSAGE_DELTA, delta_content="hello")
        h(ev)
        assert deltas == ["hello"]

    def test_assistant_message_delta_empty(self):
        deltas = []
        h = EventHandler(on_delta=lambda d: deltas.append(d))
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(SessionEventType.ASSISTANT_MESSAGE_DELTA, delta_content="")
        h(ev)
        assert deltas == []

    def test_assistant_message(self):
        h = EventHandler()
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(SessionEventType.ASSISTANT_MESSAGE, content="final text")
        h(ev)
        assert h.final_text == "final text"

    def test_session_idle_sets_done(self):
        h = EventHandler()
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(SessionEventType.SESSION_IDLE)
        h(ev)
        assert h.done.is_set()

    def test_session_error(self):
        h = EventHandler()
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(SessionEventType.SESSION_ERROR)
        h(ev)
        assert h.done.is_set()
        assert h.error is not None

    def test_tool_start_event(self):
        events = []
        h = EventHandler(on_event=lambda name, data: events.append((name, data)))
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(
            SessionEventType.TOOL_EXECUTION_START,
            tool_name="my_tool", mcp_tool_name=None, name=None,
            tool_call_id="call_1", arguments='{"a": 1}',
        )
        h(ev)
        assert len(events) == 1
        assert events[0][0] == "tool_start"
        assert events[0][1]["tool"] == "my_tool"
        assert events[0][1]["call_id"] == "call_1"

    def test_tool_complete_event(self):
        events = []
        h = EventHandler(on_event=lambda name, data: events.append((name, data)))
        from copilot.generated.session_events import SessionEventType

        start_ev = _make_event(
            SessionEventType.TOOL_EXECUTION_START,
            tool_name="tool_x", mcp_tool_name=None, name=None,
            tool_call_id="c1", arguments=None,
        )
        h(start_ev)

        result = SimpleNamespace(content="result_text")
        complete_ev = _make_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            tool_name="tool_x", mcp_tool_name=None, name=None,
            tool_call_id="c1", result=result,
        )
        h(complete_ev)
        assert events[-1][0] == "tool_done"
        assert events[-1][1]["result"] == "result_text"

    def test_tool_complete_no_result(self):
        events = []
        h = EventHandler(on_event=lambda name, data: events.append((name, data)))
        from copilot.generated.session_events import SessionEventType

        ev = _make_event(
            SessionEventType.TOOL_EXECUTION_COMPLETE,
            tool_name="t", mcp_tool_name=None, name=None,
            tool_call_id="c1", result=None,
        )
        h(ev)
        assert events[-1][1]["result"] is None

    def test_tool_progress_event(self):
        events = []
        h = EventHandler(on_event=lambda name, data: events.append((name, data)))
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(
            SessionEventType.TOOL_EXECUTION_PROGRESS,
            tool_name="t", mcp_tool_name=None, name=None,
            tool_call_id="c2", progress_message="50%",
        )
        h(ev)
        assert events[-1][0] == "tool_progress"
        assert events[-1][1]["message"] == "50%"

    def test_reasoning_event(self):
        events = []
        h = EventHandler(on_event=lambda name, data: events.append((name, data)))
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(
            SessionEventType.ASSISTANT_REASONING_DELTA,
            reasoning_text="thinking...", delta_content=None,
        )
        h(ev)
        assert events[-1][0] == "reasoning"
        assert events[-1][1]["text"] == "thinking..."

    def test_reasoning_empty_ignored(self):
        events = []
        h = EventHandler(on_event=lambda name, data: events.append((name, data)))
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(
            SessionEventType.ASSISTANT_REASONING_DELTA,
            reasoning_text="", delta_content="",
        )
        h(ev)
        assert events == []

    @patch("app.runtime.state.profile.increment_skill_usage")
    def test_skill_event(self, mock_increment):
        events = []
        h = EventHandler(on_event=lambda name, data: events.append((name, data)))
        from copilot.generated.session_events import SessionEventType

        ev = _make_event(SessionEventType.SKILL_INVOKED, name="web-search")
        h(ev)
        assert events[-1][0] == "skill"
        assert events[-1][1]["name"] == "web-search"
        mock_increment.assert_called_once_with("web-search")

    def test_subagent_events(self):
        events = []
        h = EventHandler(on_event=lambda name, data: events.append((name, data)))
        from copilot.generated.session_events import SessionEventType

        start_ev = _make_event(
            SessionEventType.SUBAGENT_STARTED,
            agent_name="sub1", agent_display_name="Sub One",
        )
        h(start_ev)
        assert events[-1][0] == "subagent_start"
        assert events[-1][1]["name"] == "sub1"

        done_ev = _make_event(
            SessionEventType.SUBAGENT_COMPLETED,
            agent_name=None, agent_display_name="Sub One",
        )
        h(done_ev)
        assert events[-1][0] == "subagent_done"
        assert events[-1][1]["name"] == "Sub One"

    def test_no_on_event_skips_dispatch(self):
        h = EventHandler()
        from copilot.generated.session_events import SessionEventType
        ev = _make_event(
            SessionEventType.TOOL_EXECUTION_START,
            tool_name="x", mcp_tool_name=None, name=None,
            tool_call_id="a", arguments=None,
        )
        h(ev)
