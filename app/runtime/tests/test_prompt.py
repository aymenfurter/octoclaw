"""Tests for the agent prompt builder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.runtime.agent.prompt import (
    _build_mcp_section,
    _build_sandbox_section,
    _load_mcp_guidance,
    build_system_prompt,
    load_soul,
    soul_exists,
)


class TestLoadSoul:
    def test_creates_placeholder_if_missing(self, data_dir: Path):
        from app.runtime.config.settings import cfg

        cfg.soul_path.parent.mkdir(parents=True, exist_ok=True)
        if cfg.soul_path.exists():
            cfg.soul_path.unlink()
        soul = load_soul()
        assert len(soul) > 0
        assert cfg.soul_path.exists()

    def test_reads_existing_soul(self, data_dir: Path):
        from app.runtime.config.settings import cfg

        cfg.soul_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.soul_path.write_text("I am a custom soul.")
        soul = load_soul()
        assert soul == "I am a custom soul."


class TestSoulExists:
    def test_returns_false_if_file_missing(self, data_dir: Path):
        from app.runtime.config.settings import cfg

        if cfg.soul_path.exists():
            cfg.soul_path.unlink()
        assert not soul_exists()

    def test_returns_false_if_placeholder(self, data_dir: Path):
        from app.runtime.config.settings import cfg

        cfg.soul_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.soul_path.write_text("This is a placeholder identity for testing.")
        assert not soul_exists()

    def test_returns_true_if_custom(self, data_dir: Path):
        from app.runtime.config.settings import cfg

        cfg.soul_path.parent.mkdir(parents=True, exist_ok=True)
        cfg.soul_path.write_text("I am a real custom agent identity.")
        assert soul_exists()


class TestBuildMcpSection:
    @patch("app.runtime.state.mcp_config.McpConfigStore")
    def test_no_servers(self, MockStore):
        MockStore.return_value.list_servers.return_value = []
        result = _build_mcp_section()
        assert "No MCP servers" in result

    @patch("app.runtime.state.mcp_config.McpConfigStore")
    def test_with_disabled_servers(self, MockStore):
        MockStore.return_value.list_servers.return_value = [
            {"name": "test", "enabled": False, "type": "http"},
        ]
        result = _build_mcp_section()
        assert "No MCP servers" in result

    @patch("app.runtime.agent.prompt._get_mcp_guidance", return_value={})
    @patch("app.runtime.state.mcp_config.McpConfigStore")
    def test_with_enabled_server(self, MockStore, mock_guidance):
        MockStore.return_value.list_servers.return_value = [
            {"name": "my-server", "enabled": True, "type": "http", "description": "My server"},
        ]
        result = _build_mcp_section()
        assert "my-server" in result
        assert "http" in result

    @patch("app.runtime.state.mcp_config.McpConfigStore")
    def test_handles_exception(self, MockStore):
        MockStore.return_value.list_servers.side_effect = RuntimeError("fail")
        result = _build_mcp_section()
        assert "No MCP" in result


class TestBuildSandboxSection:
    @patch("app.runtime.state.sandbox_config.SandboxConfigStore")
    def test_disabled(self, MockStore):
        MockStore.return_value.config.enabled = False
        result = _build_sandbox_section()
        assert result == ""

    @patch("app.runtime.state.sandbox_config.SandboxConfigStore")
    def test_error_returns_empty(self, MockStore):
        MockStore.side_effect = RuntimeError("fail")
        result = _build_sandbox_section()
        assert result == ""


class TestBuildSystemPrompt:
    @patch("app.runtime.agent.prompt._get_system_prompt_template")
    @patch("app.runtime.agent.prompt._build_sandbox_section", return_value="")
    @patch("app.runtime.agent.prompt._build_mcp_section", return_value="No MCP")
    @patch("app.runtime.state.profile.load_profile")
    @patch("app.runtime.agent.prompt.soul_exists", return_value=True)
    @patch("app.runtime.agent.prompt.load_soul", return_value="My Soul")
    def test_builds_prompt(
        self, mock_soul, mock_exists, mock_profile, mock_mcp, mock_sandbox, mock_template
    ):
        mock_profile.return_value = {"name": "TestBot", "emotional_state": "happy", "location": "Cloud"}
        mock_template.return_value = "{bootstrap}{soul}{mcp_servers}"
        result = build_system_prompt()
        assert "My Soul" in result

    @patch("app.runtime.agent.prompt._get_system_prompt_template")
    @patch("app.runtime.agent.prompt._build_sandbox_section", return_value="")
    @patch("app.runtime.agent.prompt._build_mcp_section", return_value="No MCP")
    @patch("app.runtime.state.profile.load_profile")
    @patch("app.runtime.agent.prompt.soul_exists", return_value=False)
    @patch("app.runtime.agent.prompt.load_soul", return_value="placeholder")
    def test_bootstrap_section_when_no_soul(
        self, mock_soul, mock_exists, mock_profile, mock_mcp, mock_sandbox, mock_template
    ):
        mock_profile.return_value = {"name": "", "emotional_state": "neutral"}
        mock_template.return_value = "{bootstrap}{soul}{mcp_servers}"
        result = build_system_prompt()
        assert "placeholder" in result

    @patch("app.runtime.agent.prompt._get_system_prompt_template")
    @patch("app.runtime.agent.prompt._build_sandbox_section", return_value="")
    @patch("app.runtime.agent.prompt._build_mcp_section", return_value="No MCP")
    @patch("app.runtime.state.profile.load_profile")
    @patch("app.runtime.agent.prompt.soul_exists", return_value=True)
    @patch("app.runtime.agent.prompt.load_soul", return_value="Soul")
    def test_profile_preferences(
        self, mock_soul, mock_exists, mock_profile, mock_mcp, mock_sandbox, mock_template
    ):
        mock_profile.return_value = {
            "name": "Agent",
            "emotional_state": "neutral",
            "location": "NYC",
            "preferences": {"style": "formal"},
        }
        mock_template.return_value = "{bootstrap}{soul}{mcp_servers}"
        result = build_system_prompt()
        assert "formal" in result or "Agent" in result
