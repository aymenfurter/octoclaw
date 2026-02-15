"""Tests for the CommandDispatcher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.config.settings import cfg
from app.runtime.messaging.commands import CommandContext, CommandDispatcher


@pytest.fixture()
def agent() -> AsyncMock:
    a = AsyncMock()
    a.has_session = True
    a.request_counts = {"gpt-4.1": 5}
    a.send = AsyncMock(return_value="response")
    a.new_session = AsyncMock()
    a.list_models = AsyncMock(return_value=[
        {"id": "gpt-4.1", "name": "GPT-4.1", "policy": "enabled", "billing_multiplier": 1.0, "reasoning_efforts": [], "supported_reasoning_efforts": []},
    ])
    return a


@pytest.fixture()
def dispatcher(agent: AsyncMock, data_dir: Path) -> CommandDispatcher:
    from app.runtime.state.session_store import SessionStore
    return CommandDispatcher(agent, SessionStore())


class TestTryHandle:
    @pytest.mark.asyncio
    async def test_exact_command(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        handled = await dispatcher.try_handle("/help", reply, "web")
        assert handled
        reply.assert_awaited_once()
        assert "Commands" in reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_prefix_command(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        handled = await dispatcher.try_handle("/model gpt-4.1", reply, "web")
        assert handled

    @pytest.mark.asyncio
    async def test_not_a_command(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        handled = await dispatcher.try_handle("hello there", reply, "web")
        assert not handled
        reply.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_case_insensitive(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        handled = await dispatcher.try_handle("/HELP", reply, "web")
        assert handled


class TestNewCommand:
    @pytest.mark.asyncio
    async def test_new_starts_session(self, dispatcher: CommandDispatcher, agent: AsyncMock) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/new", reply, "web")
        agent.new_session.assert_awaited_once()
        assert "New session" in reply.call_args[0][0]


class TestModelCommand:
    @pytest.mark.asyncio
    async def test_model_no_args_shows_current(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/model", reply, "web")
        msg = reply.call_args[0][0]
        assert "Current model" in msg

    @pytest.mark.asyncio
    async def test_model_with_arg_switches(self, dispatcher: CommandDispatcher, agent: AsyncMock) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/model gpt-3.5", reply, "web")
        agent.new_session.assert_awaited_once()
        msg = reply.call_args[0][0]
        assert "gpt-3.5" in msg


class TestStatusCommand:
    @pytest.mark.asyncio
    async def test_status(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/status", reply, "web")
        msg = reply.call_args[0][0]
        assert "Status" in msg
        assert "Model" in msg
        assert "Uptime" in msg


class TestSessionCommand:
    @pytest.mark.asyncio
    async def test_session_info(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/session", reply, "web")
        msg = reply.call_args[0][0]
        assert "Session" in msg


class TestSkillsCommand:
    @pytest.mark.asyncio
    async def test_skills_empty(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/skills", reply, "web")
        msg = reply.call_args[0][0]
        assert "Skills" in msg

    @pytest.mark.asyncio
    async def test_skills_with_installed(self, dispatcher: CommandDispatcher, data_dir: Path) -> None:
        d = cfg.user_skills_dir
        d.mkdir(parents=True, exist_ok=True)
        sk = d / "test-skill"
        sk.mkdir()
        (sk / "SKILL.md").write_text("# Skill")
        reply = AsyncMock()
        await dispatcher.try_handle("/skills", reply, "web")
        assert "test-skill" in reply.call_args[0][0]


class TestClearCommand:
    @pytest.mark.asyncio
    async def test_clear_memory(self, dispatcher: CommandDispatcher, data_dir: Path) -> None:
        mem_dir = cfg.memory_dir
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "file.txt").write_text("data")
        reply = AsyncMock()
        await dispatcher.try_handle("/clear", reply, "web")
        assert "cleared" in reply.call_args[0][0].lower()


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_help_lists_commands(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/help", reply, "web")
        msg = reply.call_args[0][0]
        assert "/new" in msg
        assert "/model" in msg
        assert "/skills" in msg
        assert "/help" in msg


class TestProfileCommand:
    @pytest.mark.asyncio
    async def test_profile_shows_info(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/profile", reply, "web")
        msg = reply.call_args[0][0]
        assert "Profile" in msg


class TestConfigCommand:
    @pytest.mark.asyncio
    async def test_config_no_args_shows_config(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/config", reply, "web")
        msg = reply.call_args[0][0]
        assert "Configuration" in msg

    @pytest.mark.asyncio
    async def test_config_set_allowed_key(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/config COPILOT_MODEL gpt-4o", reply, "web")
        msg = reply.call_args[0][0]
        assert "updated" in msg.lower()

    @pytest.mark.asyncio
    async def test_config_set_disallowed_key(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/config SECRET_KEY bad", reply, "web")
        msg = reply.call_args[0][0]
        assert "Cannot set" in msg


class TestSchedulesCommand:
    @pytest.mark.asyncio
    async def test_schedules_empty(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/schedules", reply, "web")
        msg = reply.call_args[0][0]
        assert "No scheduled" in msg


class TestSessionsCommand:
    @pytest.mark.asyncio
    async def test_sessions_empty(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/sessions", reply, "web")
        msg = reply.call_args[0][0]
        assert "No recorded" in msg or "sessions" in msg.lower()

    @pytest.mark.asyncio
    async def test_sessions_clear(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/sessions clear", reply, "web")
        msg = reply.call_args[0][0]
        assert "cleared" in msg.lower()


class TestSessionSubCommand:
    @pytest.mark.asyncio
    async def test_session_delete_missing(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/session delete abc123", reply, "web")
        msg = reply.call_args[0][0]
        assert "not found" in msg.lower()


class TestPhoneCommand:
    @pytest.mark.asyncio
    async def test_phone_no_args(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/phone", reply, "web")
        msg = reply.call_args[0][0]
        assert "Usage" in msg or "number" in msg.lower()

    @pytest.mark.asyncio
    async def test_phone_no_plus(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/phone 12345", reply, "web")
        assert "must start with +" in reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_phone_valid(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/phone +1234567890", reply, "web")
        assert "+1234567890" in reply.call_args[0][0]


class TestLockdownCommand:
    @pytest.mark.asyncio
    async def test_lockdown_status(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/lockdown", reply, "web")
        msg = reply.call_args[0][0]
        assert "Lock Down" in msg

    @pytest.mark.asyncio
    async def test_lockdown_invalid_action(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/lockdown maybe", reply, "web")
        msg = reply.call_args[0][0]
        assert "Usage" in msg

    @pytest.mark.asyncio
    async def test_lockdown_off_when_already_off(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/lockdown off", reply, "web")
        assert "already disabled" in reply.call_args[0][0].lower()


class TestModelsCommand:
    @pytest.mark.asyncio
    async def test_models_lists_available(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/models", reply, "web")
        msg = reply.call_args[0][0]
        assert "gpt-4.1" in msg

    @pytest.mark.asyncio
    async def test_models_empty(self, dispatcher: CommandDispatcher, agent: AsyncMock) -> None:
        agent.list_models.return_value = []
        reply = AsyncMock()
        await dispatcher.try_handle("/models", reply, "web")
        assert "No models" in reply.call_args[0][0]


class TestMcpCommand:
    @pytest.mark.asyncio
    async def test_mcp_no_servers(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/mcp", reply, "web")
        msg = reply.call_args[0][0]
        assert "No MCP" in msg or "MCP" in msg


class TestPluginsCommand:
    @pytest.mark.asyncio
    async def test_plugins_none(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/plugins", reply, "web")
        msg = reply.call_args[0][0]
        assert "No plugins" in msg or "Plugins" in msg

    @pytest.mark.asyncio
    async def test_plugin_no_args(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/plugin", reply, "web")
        assert "Usage" in reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_plugin_unknown_action(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/plugin explode test", reply, "web")
        assert "Unknown" in reply.call_args[0][0]


class TestChangeCommand:
    @pytest.mark.asyncio
    async def test_change_no_sessions(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/change", reply, "web")
        assert "No sessions" in reply.call_args[0][0]


class TestScheduleCommand:
    @pytest.mark.asyncio
    async def test_schedule_no_args(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/schedule", reply, "web")
        assert "Usage" in reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_schedule_add_too_few_args(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/schedule add 0 9", reply, "web")
        assert "Usage" in reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_schedule_add_valid(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/schedule add 0 9 * * * Do the thing", reply, "web")
        msg = reply.call_args[0][0]
        assert "Scheduled task created" in msg or "ID" in msg

    @pytest.mark.asyncio
    async def test_schedule_remove_missing(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/schedule remove abc123", reply, "web")
        assert "not found" in reply.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_schedule_remove_no_id(self, dispatcher: CommandDispatcher) -> None:
        reply = AsyncMock()
        await dispatcher.try_handle("/schedule remove", reply, "web")
        assert "Usage" in reply.call_args[0][0]
