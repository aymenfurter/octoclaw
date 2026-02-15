"""Tests for the Agent class."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.agent.agent import Agent, MAX_START_RETRIES


class TestAgentInit:
    def test_defaults(self):
        a = Agent()
        assert a._client is None
        assert a._session is None
        assert a.request_counts == {}
        assert not a.has_session

    def test_set_sandbox(self):
        a = Agent()
        mock_executor = MagicMock()
        mock_executor.enabled = True
        a.set_sandbox(mock_executor)
        assert a._sandbox is mock_executor
        assert a._interceptor is not None


class TestAgentLifecycle:
    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_start_success(self, MockClient):
        instance = AsyncMock()
        MockClient.return_value = instance
        a = Agent()
        await a.start()
        instance.start.assert_awaited_once()
        assert a._client is instance

    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_start_retries_on_timeout(self, MockClient):
        instance = AsyncMock()
        instance.start.side_effect = [TimeoutError(), None]
        MockClient.return_value = instance
        with patch("app.runtime.agent.agent.RETRY_DELAY", 0):
            a = Agent()
            await a.start()
        assert instance.start.await_count == 2

    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_start_exhausts_retries(self, MockClient):
        instance = AsyncMock()
        instance.start.side_effect = TimeoutError()
        MockClient.return_value = instance
        with patch("app.runtime.agent.agent.RETRY_DELAY", 0):
            a = Agent()
            with pytest.raises(RuntimeError, match="Could not connect"):
                await a.start()

    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_stop(self, MockClient):
        instance = AsyncMock()
        MockClient.return_value = instance
        a = Agent()
        await a.start()
        session = AsyncMock()
        a._session = session
        await a.stop()
        session.destroy.assert_awaited_once()
        instance.stop.assert_awaited_once()
        assert a._client is None
        assert a._session is None

    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_stop_handles_errors(self, MockClient):
        instance = AsyncMock()
        instance.stop.side_effect = RuntimeError("oops")
        MockClient.return_value = instance
        a = Agent()
        await a.start()
        session = AsyncMock()
        session.destroy.side_effect = RuntimeError("destroy error")
        a._session = session
        await a.stop()
        assert a._client is None


class TestAgentSession:
    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.build_system_prompt", return_value="system prompt")
    @patch("app.runtime.agent.agent.get_all_tools", return_value=[])
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_new_session(self, MockClient, mock_tools, mock_prompt):
        instance = AsyncMock()
        session = AsyncMock()
        instance.create_session.return_value = session
        MockClient.return_value = instance

        a = Agent()
        await a.start()
        result = await a.new_session()
        assert result is session
        assert a.has_session
        instance.create_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_new_session_without_start_raises(self):
        a = Agent()
        with pytest.raises(RuntimeError, match="not started"):
            await a.new_session()


class TestAgentSend:
    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.build_system_prompt", return_value="prompt")
    @patch("app.runtime.agent.agent.get_all_tools", return_value=[])
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_send_creates_session_if_needed(self, MockClient, mock_tools, mock_prompt):
        instance = AsyncMock()
        session = AsyncMock()
        instance.create_session.return_value = session

        captured_handler = None

        def mock_on(handler):
            nonlocal captured_handler
            captured_handler = handler
            return lambda: None

        async def mock_send(*args, **kwargs):
            if captured_handler:
                captured_handler.final_text = "reply"
                captured_handler.done.set()

        session.on = mock_on
        session.send = mock_send
        MockClient.return_value = instance

        a = Agent()
        await a.start()
        result = await a.send("hello")
        assert result is not None


class TestAgentListModels:
    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_list_models(self, MockClient):
        model = SimpleNamespace(
            id="gpt-4.1",
            name="GPT-4.1",
            policy=SimpleNamespace(state="enabled"),
            billing=SimpleNamespace(multiplier=1.0),
            supported_reasoning_efforts=["low", "high"],
        )
        instance = AsyncMock()
        instance.list_models.return_value = [model]
        MockClient.return_value = instance

        a = Agent()
        await a.start()
        models = await a.list_models()
        assert len(models) == 1
        assert models[0]["id"] == "gpt-4.1"

    @pytest.mark.asyncio
    @patch("app.runtime.agent.agent.CopilotClient")
    async def test_list_models_failure(self, MockClient):
        instance = AsyncMock()
        instance.list_models.side_effect = RuntimeError("fail")
        MockClient.return_value = instance

        a = Agent()
        await a.start()
        models = await a.list_models()
        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_not_started(self):
        a = Agent()
        with pytest.raises(RuntimeError, match="not started"):
            await a.list_models()


class TestBuildSessionConfig:
    @patch("app.runtime.agent.agent.build_system_prompt", return_value="sp")
    @patch("app.runtime.agent.agent.get_all_tools", return_value=[])
    @patch("app.runtime.agent.agent.McpConfigStore")
    def test_basic_config(self, MockMcp, mock_tools, mock_prompt):
        MockMcp.return_value.get_enabled_servers.return_value = {}
        a = Agent()
        config = a._build_session_config()
        assert config["model"] is not None
        assert config["streaming"] is True
        assert "system_message" in config
        assert "hooks" in config

    @patch("app.runtime.agent.agent.build_system_prompt", return_value="sp")
    @patch("app.runtime.agent.agent.get_all_tools", return_value=[])
    @patch("app.runtime.agent.agent.McpConfigStore")
    def test_config_with_sandbox(self, MockMcp, mock_tools, mock_prompt):
        MockMcp.return_value.get_enabled_servers.return_value = {}
        a = Agent()
        executor = MagicMock()
        executor.enabled = True
        a.set_sandbox(executor)
        config = a._build_session_config()
        assert "excluded_tools" in config

    @patch("app.runtime.agent.agent.build_system_prompt", return_value="sp")
    @patch("app.runtime.agent.agent.get_all_tools", return_value=[])
    @patch("app.runtime.agent.agent.McpConfigStore")
    def test_mcp_fallback_on_error(self, MockMcp, mock_tools, mock_prompt):
        MockMcp.return_value.get_enabled_servers.side_effect = RuntimeError("fail")
        a = Agent()
        config = a._build_session_config()
        assert "playwright" in config["mcp_servers"]
