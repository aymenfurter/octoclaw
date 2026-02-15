"""Tests for server route handlers using aiohttp TestClient."""

from __future__ import annotations

from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, TestClient, TestServer

from app.runtime.scheduler import Scheduler
from app.runtime.server.routes.mcp_routes import McpRoutes
from app.runtime.server.routes.profile_routes import ProfileRoutes
from app.runtime.server.routes.scheduler_routes import SchedulerRoutes
from app.runtime.server.routes.session_routes import SessionRoutes
from app.runtime.state.mcp_config import McpConfigStore
from app.runtime.state.profile import save_profile
from app.runtime.state.session_store import SessionStore


def _build_app(setup_fn) -> web.Application:
    app = web.Application()
    setup_fn(app.router)
    return app


# -- Scheduler Routes ---

class TestSchedulerRoutes:
    @pytest.fixture()
    def scheduler(self, tmp_path: Path) -> Scheduler:
        return Scheduler(path=tmp_path / "sched.json")

    @pytest.fixture()
    def routes(self, scheduler: Scheduler) -> SchedulerRoutes:
        return SchedulerRoutes(scheduler)

    @pytest.mark.asyncio
    async def test_list_empty(self, routes: SchedulerRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/schedules")
            assert resp.status == 200
            data = await resp.json()
            assert data == []

    @pytest.mark.asyncio
    async def test_create_task(self, routes: SchedulerRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/schedules", json={
                "description": "Test task",
                "prompt": "Do stuff",
                "cron": "0 9 * * *",
            })
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
            assert data["task"]["description"] == "Test task"

    @pytest.mark.asyncio
    async def test_create_invalid_cron(self, routes: SchedulerRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/schedules", json={
                "description": "Bad",
                "prompt": "x",
                "cron": "* * * * *",
            })
            assert resp.status == 400

    @pytest.mark.asyncio
    async def test_update_task(self, routes: SchedulerRoutes, scheduler: Scheduler) -> None:
        task = scheduler.add(description="old", prompt="x", cron="0 9 * * *")
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(f"/api/schedules/{task.id}", json={"description": "new"})
            assert resp.status == 200
            data = await resp.json()
            assert data["task"]["description"] == "new"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, routes: SchedulerRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put("/api/schedules/nope", json={"description": "x"})
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_delete_task(self, routes: SchedulerRoutes, scheduler: Scheduler) -> None:
        task = scheduler.add(description="del", prompt="x", cron="0 9 * * *")
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete(f"/api/schedules/{task.id}")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, routes: SchedulerRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/schedules/nope")
            assert resp.status == 404


# -- Session Routes ---

class TestSessionRoutes:
    @pytest.fixture()
    def store(self, data_dir: Path) -> SessionStore:
        return SessionStore()

    @pytest.fixture()
    def routes(self, store: SessionStore) -> SessionRoutes:
        return SessionRoutes(store)

    @pytest.mark.asyncio
    async def test_list_empty(self, routes: SessionRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions")
            assert resp.status == 200
            assert await resp.json() == []

    @pytest.mark.asyncio
    async def test_create_and_list(self, routes: SessionRoutes, store: SessionStore) -> None:
        store.start_session("sess-1", model="gpt-4.1")
        store.record("user", "hello")
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions")
            data = await resp.json()
            assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_session(self, routes: SessionRoutes, store: SessionStore) -> None:
        store.start_session("sess-2", model="gpt-4.1")
        store.record("user", "hi")
        sessions = store.list_sessions()
        sid = sessions[0]["id"]
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/api/sessions/{sid}")
            assert resp.status == 200
            data = await resp.json()
            assert data["id"] == sid

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, routes: SessionRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/nope")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_delete_session(self, routes: SessionRoutes, store: SessionStore) -> None:
        store.start_session("sess-3", model="gpt-4.1")
        store.record("user", "hi")
        sid = store.list_sessions()[0]["id"]
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete(f"/api/sessions/{sid}")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, routes: SessionRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/sessions/nope")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_clear_sessions(self, routes: SessionRoutes, store: SessionStore) -> None:
        store.start_session("sess-4", model="gpt-4.1")
        store.record("user", "hi")
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/sessions")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_stats(self, routes: SessionRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/stats")
            assert resp.status == 200
            data = await resp.json()
            assert "total_sessions" in data

    @pytest.mark.asyncio
    async def test_get_policy(self, routes: SessionRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/sessions/policy")
            assert resp.status == 200
            data = await resp.json()
            assert "policy" in data
            assert "options" in data

    @pytest.mark.asyncio
    async def test_set_policy(self, routes: SessionRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put("/api/sessions/policy", json={"policy": "never"})
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_set_invalid_policy(self, routes: SessionRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put("/api/sessions/policy", json={"policy": "invalid"})
            assert resp.status == 400


# -- Profile Routes ---

class TestProfileRoutes:
    @pytest.fixture()
    def routes(self) -> ProfileRoutes:
        return ProfileRoutes()

    @pytest.mark.asyncio
    async def test_get_profile(self, routes: ProfileRoutes, data_dir: Path) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/profile")
            assert resp.status == 200
            data = await resp.json()
            assert "name" in data

    @pytest.mark.asyncio
    async def test_update_profile(self, routes: ProfileRoutes, data_dir: Path) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/profile", json={"name": "TestBot", "location": "Cloud"})
            assert resp.status == 200
            resp2 = await client.get("/api/profile")
            data = await resp2.json()
            assert data["name"] == "TestBot"

    @pytest.mark.asyncio
    async def test_update_preferences(self, routes: ProfileRoutes, data_dir: Path) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/profile", json={
                "preferences": {"theme": "dark"},
            })
            assert resp.status == 200


# -- MCP Routes ---

class TestMcpRoutes:
    @pytest.fixture()
    def store(self, data_dir: Path) -> McpConfigStore:
        return McpConfigStore()

    @pytest.fixture()
    def routes(self, store: McpConfigStore) -> McpRoutes:
        return McpRoutes(store)

    @pytest.mark.asyncio
    async def test_list_empty(self, routes: McpRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/mcp/servers")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_add_server(self, routes: McpRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/mcp/servers", json={
                "name": "test-mcp",
                "type": "http",
                "url": "http://localhost:8080",
            })
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_get_server(self, routes: McpRoutes, store: McpConfigStore) -> None:
        store.add_server("test-srv", "http", url="http://example.com")
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/mcp/servers/test-srv")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, routes: McpRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/mcp/servers/nope")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_enable_disable(self, routes: McpRoutes, store: McpConfigStore) -> None:
        store.add_server("toggle", "http", url="http://example.com")
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/mcp/servers/toggle/disable")
            assert resp.status == 200
            resp = await client.post("/api/mcp/servers/toggle/enable")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_enable_nonexistent(self, routes: McpRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/mcp/servers/nope/enable")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_remove_server(self, routes: McpRoutes, store: McpConfigStore) -> None:
        store.add_server("removable", "http", url="http://example.com")
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/mcp/servers/removable")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, routes: McpRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.delete("/api/mcp/servers/nope")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_update_server(self, routes: McpRoutes, store: McpConfigStore) -> None:
        store.add_server("updatable", "http", url="http://example.com")
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put("/api/mcp/servers/updatable", json={
                "description": "Updated desc",
            })
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, routes: McpRoutes) -> None:
        app = _build_app(routes.register)
        async with TestClient(TestServer(app)) as client:
            resp = await client.put("/api/mcp/servers/nope", json={"description": "x"})
            assert resp.status == 404
