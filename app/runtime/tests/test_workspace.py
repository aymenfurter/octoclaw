"""Tests for the WorkspaceHandler."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app.runtime.server.workspace import WorkspaceHandler


def _make_app(data_dir: Path) -> web.Application:
    handler = WorkspaceHandler()
    handler.ROOTS = {"data": data_dir}
    app = web.Application()
    handler.register(app.router)
    return app


@pytest.fixture
async def client(tmp_path: Path) -> TestClient:
    data_dir = tmp_path / "workspace_data"
    data_dir.mkdir()
    (data_dir / "hello.txt").write_text("world")
    sub = data_dir / "subdir"
    sub.mkdir()
    (sub / "nested.json").write_text('{"key": "value"}')
    app = _make_app(data_dir)
    async with TestClient(TestServer(app)) as c:
        yield c


@pytest.mark.asyncio
class TestWorkspaceListDir:
    async def test_list_root(self, client: TestClient) -> None:
        resp = await client.get("/api/workspace/list?path=data")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        names = {e["name"] for e in data["entries"]}
        assert "hello.txt" in names
        assert "subdir" in names

    async def test_list_subdir(self, client: TestClient) -> None:
        resp = await client.get("/api/workspace/list?path=data/subdir")
        assert resp.status == 200
        data = await resp.json()
        names = {e["name"] for e in data["entries"]}
        assert "nested.json" in names

    async def test_list_invalid_root(self, client: TestClient) -> None:
        resp = await client.get("/api/workspace/list?path=invalid")
        assert resp.status == 400


@pytest.mark.asyncio
class TestWorkspaceReadFile:
    async def test_read_file(self, client: TestClient) -> None:
        resp = await client.get("/api/workspace/read?path=data/hello.txt")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert data["content"] == "world"
        assert not data["binary"]

    async def test_read_missing_path(self, client: TestClient) -> None:
        resp = await client.get("/api/workspace/read")
        assert resp.status == 400

    async def test_read_nonexistent(self, client: TestClient) -> None:
        resp = await client.get("/api/workspace/read?path=data/nope.txt")
        assert resp.status == 404

    async def test_read_nested(self, client: TestClient) -> None:
        resp = await client.get("/api/workspace/read?path=data/subdir/nested.json")
        assert resp.status == 200
        data = await resp.json()
        assert '"key"' in data["content"]
