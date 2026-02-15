"""Tests for BotEndpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app.runtime.server.bot_endpoint import BotEndpoint


@pytest.fixture()
def endpoint() -> BotEndpoint:
    adapter = AsyncMock()
    adapter.process_activity = AsyncMock(return_value=None)
    bot = AsyncMock()
    return BotEndpoint(adapter, bot)


def _patch_bot_creds():
    """Patch cfg in bot_endpoint module to report bot credentials as configured."""
    return patch.multiple(
        "app.runtime.server.bot_endpoint.cfg",
        bot_app_id="test-id",
        bot_app_password="test-pw",
    )


class TestHandle:
    @pytest.mark.asyncio
    async def test_no_credentials(self, endpoint: BotEndpoint, data_dir: Path) -> None:
        app = web.Application()
        endpoint.register(app.router)
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/messages", json={"type": "message"})
            assert resp.status == 503
            data = await resp.json()
            assert "not configured" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_success(self, endpoint: BotEndpoint, data_dir: Path) -> None:
        with _patch_bot_creds():
            app = web.Application()
            endpoint.register(app.router)
            async with TestClient(TestServer(app)) as client:
                resp = await client.post(
                    "/api/messages",
                    json={"type": "message", "text": "hello"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status == 200

    @pytest.mark.asyncio
    async def test_process_returns_response(self, endpoint: BotEndpoint, data_dir: Path) -> None:
        with _patch_bot_creds():
            mock_response = MagicMock()
            mock_response.status = 201
            mock_response.body = b'{"ok": true}'
            endpoint.adapter.process_activity.return_value = mock_response
            app = web.Application()
            endpoint.register(app.router)
            async with TestClient(TestServer(app)) as client:
                resp = await client.post(
                    "/api/messages",
                    json={"type": "message"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status == 201

    @pytest.mark.asyncio
    async def test_permission_error(self, endpoint: BotEndpoint, data_dir: Path) -> None:
        with _patch_bot_creds():
            endpoint.adapter.process_activity.side_effect = PermissionError("denied")
            app = web.Application()
            endpoint.register(app.router)
            async with TestClient(TestServer(app)) as client:
                resp = await client.post(
                    "/api/messages",
                    json={"type": "message"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status == 401

    @pytest.mark.asyncio
    async def test_internal_error(self, endpoint: BotEndpoint, data_dir: Path) -> None:
        with _patch_bot_creds():
            endpoint.adapter.process_activity.side_effect = RuntimeError("boom")
            app = web.Application()
            endpoint.register(app.router)
            async with TestClient(TestServer(app)) as client:
                resp = await client.post(
                    "/api/messages",
                    json={"type": "message"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status == 500

    @pytest.mark.asyncio
    async def test_get_messages_probe(self, endpoint: BotEndpoint) -> None:
        app = web.Application()
        endpoint.register(app.router)
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/messages")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
            assert data["method"] == "POST required"

    @pytest.mark.asyncio
    async def test_passes_activity_object(self, endpoint: BotEndpoint, data_dir: Path) -> None:
        """process_activity must receive an Activity, not a raw dict."""
        from botbuilder.schema import Activity

        with _patch_bot_creds():
            app = web.Application()
            endpoint.register(app.router)
            async with TestClient(TestServer(app)) as client:
                resp = await client.post(
                    "/api/messages",
                    json={"type": "message", "text": "hi", "channelId": "telegram"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status == 200
                call_args = endpoint.adapter.process_activity.call_args
                activity_arg = call_args[0][0]
                assert isinstance(activity_arg, Activity)
                assert activity_arg.type == "message"
                assert activity_arg.channel_id == "telegram"
