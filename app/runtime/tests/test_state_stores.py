"""Tests for state stores: MCP, Sandbox, Plugin, FoundryIQ, InfraConfig."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.runtime.state.mcp_config import McpConfigStore
from app.runtime.state.sandbox_config import BLACKLIST, DEFAULT_WHITELIST, SandboxConfigStore
from app.runtime.state.plugin_config import PluginConfigStore
from app.runtime.state.foundry_iq_config import FoundryIQConfigStore
from app.runtime.state.infra_config import InfraConfigStore


class TestMcpConfigStore:
    def test_initial_builtin_servers(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        servers = store.list_servers()
        names = {s["name"] for s in servers}
        assert "playwright" in names

    def test_add_server(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        result = store.add_server("my-server", "http", url="https://example.com/mcp")
        assert result["name"] == "my-server"
        assert store.get_server("my-server") is not None

    def test_add_server_missing_name(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        with pytest.raises(ValueError):
            store.add_server("", "http", url="https://example.com")

    def test_add_server_invalid_type(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        with pytest.raises(ValueError):
            store.add_server("bad", "invalid")

    def test_add_local_no_command(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        with pytest.raises(ValueError):
            store.add_server("bad", "local")

    def test_add_http_no_url(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        with pytest.raises(ValueError):
            store.add_server("bad", "http")

    def test_update_server(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        store.add_server("test", "http", url="https://example.com")
        updated = store.update_server("test", description="Updated")
        assert updated is not None
        assert updated["description"] == "Updated"

    def test_update_nonexistent(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        assert store.update_server("nope") is None

    def test_set_enabled(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        store.add_server("test", "http", url="https://example.com")
        assert store.set_enabled("test", False)
        assert not store.get_server("test")["enabled"]

    def test_remove_server(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        store.add_server("removable", "http", url="https://example.com")
        assert store.remove_server("removable")
        assert store.get_server("removable") is None

    def test_remove_builtin_raises(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        with pytest.raises(ValueError, match="built-in"):
            store.remove_server("playwright")

    def test_get_enabled_servers(self, tmp_path: Path) -> None:
        store = McpConfigStore(path=tmp_path / "mcp.json")
        enabled = store.get_enabled_servers()
        assert "playwright" in enabled

    def test_persistence(self, tmp_path: Path) -> None:
        db = tmp_path / "mcp.json"
        s1 = McpConfigStore(path=db)
        s1.add_server("persist", "http", url="https://example.com")
        s2 = McpConfigStore(path=db)
        assert s2.get_server("persist") is not None


class TestSandboxConfigStore:
    def test_defaults(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        assert not store.enabled
        assert store.sync_data
        assert store.whitelist == DEFAULT_WHITELIST

    def test_set_enabled(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        store.set_enabled(True)
        assert store.enabled

    def test_set_sync_data(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        store.set_sync_data(False)
        assert not store.sync_data

    def test_add_whitelist_item(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        assert store.add_whitelist_item("custom_dir")
        assert "custom_dir" in store.whitelist

    def test_add_blacklisted_item(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        item = next(iter(BLACKLIST))
        assert not store.add_whitelist_item(item)

    def test_remove_whitelist_item(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        first = store.whitelist[0]
        store.remove_whitelist_item(first)
        assert first not in store.whitelist

    def test_reset_whitelist(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        store.add_whitelist_item("custom")
        store.reset_whitelist()
        assert store.whitelist == DEFAULT_WHITELIST

    def test_set_pool_metadata(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        store.set_pool_metadata(
            resource_group="rg", location="eastus",
            pool_name="pool1", pool_id="/subs/x", endpoint="https://x.com"
        )
        assert store.is_provisioned
        assert store.pool_name == "pool1"

    def test_clear_pool_metadata(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        store.set_pool_metadata(
            resource_group="rg", location="eastus",
            pool_name="pool1", pool_id="/subs/x", endpoint="https://x.com"
        )
        store.clear_pool_metadata()
        assert not store.is_provisioned

    def test_to_dict(self, tmp_path: Path) -> None:
        store = SandboxConfigStore(path=tmp_path / "sandbox.json")
        d = store.to_dict()
        assert "enabled" in d
        assert "whitelist" in d

    def test_persistence(self, tmp_path: Path) -> None:
        db = tmp_path / "sandbox.json"
        s1 = SandboxConfigStore(path=db)
        s1.set_enabled(True)
        s2 = SandboxConfigStore(path=db)
        assert s2.enabled


class TestPluginConfigStore:
    def test_empty(self, tmp_path: Path) -> None:
        store = PluginConfigStore(path=tmp_path / "plugins.json")
        assert store.list_states() == {}

    def test_get_default_state(self, tmp_path: Path) -> None:
        store = PluginConfigStore(path=tmp_path / "plugins.json")
        state = store.get_state("my-plugin")
        assert not state["enabled"]
        assert not state["setup_completed"]

    def test_set_enabled(self, tmp_path: Path) -> None:
        store = PluginConfigStore(path=tmp_path / "plugins.json")
        store.set_enabled("test-plugin", True)
        assert store.get_state("test-plugin")["enabled"]
        assert store.get_state("test-plugin")["installed_at"] is not None

    def test_mark_setup_completed(self, tmp_path: Path) -> None:
        store = PluginConfigStore(path=tmp_path / "plugins.json")
        store.mark_setup_completed("p1")
        assert store.get_state("p1")["setup_completed"]

    def test_reset(self, tmp_path: Path) -> None:
        store = PluginConfigStore(path=tmp_path / "plugins.json")
        store.set_enabled("p1", True)
        store.reset("p1")
        assert not store.get_state("p1")["enabled"]

    def test_persistence(self, tmp_path: Path) -> None:
        db = tmp_path / "plugins.json"
        s1 = PluginConfigStore(path=db)
        s1.set_enabled("p1", True)
        s2 = PluginConfigStore(path=db)
        assert s2.get_state("p1")["enabled"]


class TestFoundryIQConfigStore:
    def test_defaults(self, tmp_path: Path) -> None:
        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        assert not store.enabled
        assert not store.is_configured
        assert not store.is_provisioned

    def test_save_and_load(self, tmp_path: Path) -> None:
        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        store.save(
            enabled=True,
            search_endpoint="https://search.example.com",
            search_api_key="key1",
            embedding_endpoint="https://embed.example.com",
            embedding_api_key="key2",
        )
        assert store.enabled
        assert store.is_configured

    def test_safe_dict_masks_keys(self, tmp_path: Path) -> None:
        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        store.save(search_api_key="secret", embedding_api_key="secret2")
        safe = store.to_safe_dict()
        assert safe["search_api_key"] == "****"
        assert safe["embedding_api_key"] == "****"

    def test_set_last_indexed(self, tmp_path: Path) -> None:
        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        store.set_last_indexed("2024-01-01T00:00:00Z")
        assert store.config.last_indexed_at == "2024-01-01T00:00:00Z"

    def test_clear_provisioning(self, tmp_path: Path) -> None:
        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        store.save(provisioned=True, search_endpoint="https://x.com")
        store.clear_provisioning()
        assert not store.is_provisioned
        assert not store.enabled

    def test_enabled_string_coercion(self, tmp_path: Path) -> None:
        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        store.save(enabled="true")
        assert store.enabled
        store.save(enabled="false")
        assert not store.enabled

    def test_persistence(self, tmp_path: Path) -> None:
        db = tmp_path / "fiq.json"
        s1 = FoundryIQConfigStore(path=db)
        s1.save(enabled=True)
        s2 = FoundryIQConfigStore(path=db)
        assert s2.enabled


class TestInfraConfigStore:
    def test_defaults(self, tmp_path: Path) -> None:
        store = InfraConfigStore(path=tmp_path / "infra.json")
        assert store.bot.resource_group == "octoclaw-rg"
        assert not store.telegram_configured
        assert not store.voice_call_configured

    def test_save_bot(self, tmp_path: Path) -> None:
        store = InfraConfigStore(path=tmp_path / "infra.json")
        store.save_bot(display_name="TestBot", location="westus")
        assert store.bot.display_name == "TestBot"
        assert store.bot.location == "westus"

    def test_save_telegram(self, tmp_path: Path) -> None:
        store = InfraConfigStore(path=tmp_path / "infra.json")
        store.save_telegram(token="123:ABC")
        assert store.telegram_configured
        assert store.channels.telegram.token == "123:ABC"

    def test_clear_telegram(self, tmp_path: Path) -> None:
        store = InfraConfigStore(path=tmp_path / "infra.json")
        store.save_telegram(token="xyz")
        store.clear_telegram()
        assert not store.telegram_configured

    def test_save_voice_call(self, tmp_path: Path) -> None:
        store = InfraConfigStore(path=tmp_path / "infra.json")
        store.save_voice_call(acs_connection_string="endpoint=sb://x;SharedAccessKey=y")
        assert store.voice_call_configured

    def test_clear_voice_call(self, tmp_path: Path) -> None:
        store = InfraConfigStore(path=tmp_path / "infra.json")
        store.save_voice_call(acs_connection_string="x")
        store.clear_voice_call()
        assert not store.voice_call_configured

    def test_to_safe_dict(self, tmp_path: Path) -> None:
        store = InfraConfigStore(path=tmp_path / "infra.json")
        store.save_telegram(token="secret-token")
        safe = store.to_safe_dict()
        assert safe["channels"]["telegram"]["token"] == "****"

    def test_persistence(self, tmp_path: Path) -> None:
        db = tmp_path / "infra.json"
        s1 = InfraConfigStore(path=db)
        s1.save_bot(display_name="Persist")
        s2 = InfraConfigStore(path=db)
        assert s2.bot.display_name == "Persist"
