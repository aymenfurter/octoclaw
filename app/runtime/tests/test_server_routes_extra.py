"""Tests for plugin, skill, env, proactive, and sandbox server routes."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app.runtime.server.routes.plugin_routes import PluginRoutes
from app.runtime.server.routes.proactive_routes import ProactiveRoutes
from app.runtime.server.routes.skill_routes import SkillRoutes
from app.runtime.state.plugin_config import PluginConfigStore
from app.runtime.state.proactive import ProactiveStore


def _build_app(setup_fn) -> web.Application:
    app = web.Application()
    setup_fn(app.router)
    return app


# -- Plugin Routes ---------------------------------------------------------

class TestPluginRoutes:
    @pytest.fixture()
    def config_store(self) -> PluginConfigStore:
        return PluginConfigStore()

    @pytest.fixture()
    def registry(self, data_dir: Path):
        from app.runtime.registries.plugins import PluginRegistry

        (data_dir / "plugins").mkdir(parents=True, exist_ok=True)
        return PluginRegistry()

    @pytest.fixture()
    def routes(self, registry, config_store) -> PluginRoutes:
        return PluginRoutes(registry, config_store)

    @pytest.mark.asyncio
    async def test_list_plugins(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/plugins")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
            assert isinstance(data["plugins"], list)

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/plugins/nonexistent")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_enable_nonexistent(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/plugins/nonexistent/enable")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_disable(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/plugins/some-plugin/disable")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_setup_content_nonexistent(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/plugins/nonexistent/setup")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_complete_setup_nonexistent(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/plugins/nonexistent/setup")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/plugins/nonexistent")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_import_empty_body(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/plugins/import", data=b"")
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_import_invalid_zip(self, routes: PluginRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/plugins/import", data=b"not a zip")
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_import_zip_no_manifest(self, routes: PluginRoutes) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "hello")
        buf.seek(0)
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/plugins/import", data=buf.read())
            assert resp.status == 400
            data = await resp.json()
            assert "No manifest" in data["message"]

    @pytest.mark.asyncio
    async def test_import_zip_missing_id(self, routes: PluginRoutes) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"name": "test"}))
        buf.seek(0)
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/plugins/import", data=buf.read())
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_import_valid_zip(self, routes: PluginRoutes, registry) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"id": "test-plugin", "name": "Test"}))
        buf.seek(0)
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/plugins/import", data=buf.read())
            assert resp.status == 200
            data = await resp.json()
            assert data["plugin_id"] == "test-plugin"

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, routes: PluginRoutes, registry, config_store, data_dir) -> None:
        from app.runtime.config.settings import cfg

        plugin_dir = cfg.data_dir / "plugins" / "my-plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "manifest.json").write_text(json.dumps({
            "id": "my-plugin",
            "name": "My Plugin",
            "version": "1.0",
            "description": "A test plugin",
        }))
        # also write PLUGIN.json (the canonical name)
        (plugin_dir / "PLUGIN.json").write_text(json.dumps({
            "id": "my-plugin",
            "name": "My Plugin",
            "version": "1.0",
            "description": "A test plugin",
        }))
        registry.refresh()

        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/plugins")
            data = await resp.json()
            assert any(p["id"] == "my-plugin" for p in data["plugins"])

            resp = await client.get("/api/plugins/my-plugin")
            assert resp.status == 200

            resp = await client.post("/api/plugins/my-plugin/enable")
            assert resp.status == 200

            resp = await client.get("/api/plugins/my-plugin/setup")
            assert resp.status == 200

            resp = await client.post("/api/plugins/my-plugin/setup")
            assert resp.status == 200

            resp = await client.post("/api/plugins/my-plugin/disable")
            assert resp.status == 200

            resp = await client.delete("/api/plugins/my-plugin")
            assert resp.status == 200


# -- Skill Routes ----------------------------------------------------------

class TestSkillRoutes:
    @pytest.fixture()
    def registry(self, data_dir: Path):
        from app.runtime.registries.skills import SkillRegistry

        return SkillRegistry()

    @pytest.fixture()
    def routes(self, registry) -> SkillRoutes:
        return SkillRoutes(registry)

    @pytest.mark.asyncio
    async def test_installed_empty(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/skills/installed")
            assert resp.status == 200
            assert await resp.json() == []

    @pytest.mark.asyncio
    async def test_catalog(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/skills/catalog")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_install_missing_url(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/skills/install", json={"url": ""})
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_install_nonexistent_url(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/skills/install",
                json={"url": "https://example.com/nonexistent.md"},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/skills/no-such-skill")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_contribute_missing_skill_id(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/skills/contribute", json={"skill_id": ""})
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_contribute_nonexistent(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/skills/contribute", json={"skill_id": "no-such"}
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_installed_with_skill(self, routes, registry, data_dir) -> None:
        from app.runtime.config.settings import cfg

        skill_dir = cfg.user_skills_dir / "test-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\ntitle: Test Skill\ndescription: A test\n---\nDo something."
        )
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/skills/installed")
            assert resp.status == 200
            data = await resp.json()
            assert len(data) >= 1


# -- Proactive Routes ------------------------------------------------------

class TestProactiveRoutes:
    @pytest.fixture()
    def store(self) -> ProactiveStore:
        return ProactiveStore()

    @pytest.fixture()
    def conv_store(self):
        mock = MagicMock()
        mock.count = 0
        mock.get_all.return_value = []
        return mock

    @pytest.fixture()
    def routes(self, store, conv_store) -> ProactiveRoutes:
        return ProactiveRoutes(store, conv_store=conv_store)

    @pytest.mark.asyncio
    async def test_get_state(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/proactive")
            assert resp.status == 200
            data = await resp.json()
            assert "enabled" in data
            assert "memory" in data

    @pytest.mark.asyncio
    async def test_set_enabled(self, routes, store) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(
                "/api/proactive/enabled",
                json={"enabled": True},
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["enabled"] is True
            assert store.enabled is True

    @pytest.mark.asyncio
    async def test_cancel_pending_none(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/proactive/pending")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "none"

    @pytest.mark.asyncio
    async def test_update_preferences(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(
                "/api/proactive/preferences",
                json={"min_gap_hours": 4, "max_daily": 3},
            )
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_record_reaction(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/proactive/reaction",
                json={"reaction": "positive", "detail": "great"},
            )
            assert resp.status in (200, 404)

    @pytest.mark.asyncio
    async def test_dry_run_no_adapter(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/proactive/dry-run")
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_dry_run_no_refs(self, store, conv_store) -> None:
        adapter = AsyncMock()
        routes = ProactiveRoutes(store, adapter=adapter, conv_store=conv_store)
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/proactive/dry-run")
            assert resp.status == 200
            data = await resp.json()
            assert data["conversation_refs"] == 0


# -- Environment Routes (without Azure) ---

class TestEnvironmentRoutes:
    @pytest.fixture()
    def deploy_store(self):
        from app.runtime.state.deploy_state import DeployStateStore

        return DeployStateStore()

    @pytest.fixture()
    def routes(self, deploy_store):
        from app.runtime.server.routes.env_routes import EnvironmentRoutes

        return EnvironmentRoutes(deploy_store, az=None)

    @pytest.mark.asyncio
    async def test_list_deployments(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/environments")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/environments/nope")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_destroy_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/environments/test-deploy")
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_cleanup_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/environments/test-deploy/cleanup")
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_remove_record_nonexistent(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/environments/nope/record")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_audit_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/environments/audit")
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_audit_cleanup_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/environments/audit/cleanup")
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_misconfig_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/environments/misconfig",
                json={},
            )
            assert resp.status == 500


# -- Sandbox Routes (without Azure) ---

class TestSandboxRoutes:
    @pytest.fixture()
    def config_store(self):
        from app.runtime.state.sandbox_config import SandboxConfigStore

        return SandboxConfigStore()

    @pytest.fixture()
    def executor(self, config_store):
        from app.runtime.sandbox import SandboxExecutor

        return SandboxExecutor(config_store)

    @pytest.fixture()
    def routes(self, config_store, executor):
        from app.runtime.server.routes.sandbox_routes import SandboxRoutes

        return SandboxRoutes(config_store, executor, az=None)

    @pytest.mark.asyncio
    async def test_get_config(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sandbox/config")
            assert resp.status == 200
            data = await resp.json()
            assert "blacklist" in data
            assert "default_whitelist" in data
            assert "warnings" in data

    @pytest.mark.asyncio
    async def test_update_config_enable(self, routes, config_store) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                json={"enabled": True},
            )
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_update_config_sync_data(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                json={"sync_data": True},
            )
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_update_config_whitelist(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                json={"whitelist": ["echo", "ls"]},
            )
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_update_config_add_blacklisted(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                json={"add_whitelist": ".azure"},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_update_config_remove_whitelist(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                json={"remove_whitelist": "echo"},
            )
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_update_config_reset_whitelist(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                json={"reset_whitelist": True},
            )
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_update_config_invalid_json(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                data=b"not json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_update_config_whitelist_not_list(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                json={"whitelist": "not-a-list"},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_test_sandbox_no_endpoint(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/sandbox/test", json={})
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_provision_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/sandbox/provision", json={})
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_remove_pool_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/sandbox/provision")
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_update_endpoint(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/sandbox/config",
                json={"session_pool_endpoint": "https://example.com/pool"},
            )
            assert resp.status == 200


# -- Foundry IQ Routes (without Azure) ---

class TestFoundryIQRoutes:
    @pytest.fixture()
    def config_store(self):
        from app.runtime.state.foundry_iq_config import FoundryIQConfigStore

        return FoundryIQConfigStore()

    @pytest.fixture()
    def routes(self, config_store):
        from app.runtime.server.routes.foundry_iq_routes import FoundryIQRoutes

        return FoundryIQRoutes(config_store, az=None)

    @pytest.mark.asyncio
    async def test_get_config(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/foundry-iq/config")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_save_config(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(
                "/api/foundry-iq/config",
                json={"enabled": True},
            )
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_search_missing_query(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/foundry-iq/search",
                json={"query": ""},
            )
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_provision_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/foundry-iq/provision", json={})
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_decommission_no_az(self, routes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/foundry-iq/provision")
            assert resp.status == 500

    @pytest.mark.asyncio
    async def test_decommission_not_provisioned(self, routes) -> None:
        from app.runtime.server.routes.foundry_iq_routes import FoundryIQRoutes

        mock_az = MagicMock()
        routes_with_az = FoundryIQRoutes(routes._store, az=mock_az)
        app = _build_app(routes_with_az.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/foundry-iq/provision")
            assert resp.status == 400
