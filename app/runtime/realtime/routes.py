"""HTTP / WebSocket routes for the Realtime voice call feature."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from .auth import validate_acs_request
from .caller import AcsCaller
from .middleware import RealtimeMiddleTier

logger = logging.getLogger(__name__)


class RealtimeRoutes:
    """Registers all voice-call related routes."""

    def __init__(
        self,
        caller: AcsCaller,
        middleware: RealtimeMiddleTier,
        *,
        callback_token: str = "",
        acs_resource_id: str = "",
    ) -> None:
        self._caller = caller
        self._middleware = middleware
        self._callback_token = callback_token
        self._acs_resource_id = acs_resource_id

    def register(self, router: web.UrlDispatcher) -> None:
        router.add_post("/acs", self._acs_callback)
        router.add_post("/acs/incoming", self._acs_incoming)
        router.add_get("/realtime-acs", self._ws_handler_acs)
        router.add_post("/api/voice/call", self._api_call)
        router.add_get("/api/voice/status", self._api_status)

    async def _acs_callback(self, request: web.Request) -> web.Response:
        logger.info("ACS callback: path=%s content_type=%s", request.path, request.content_type)
        if self._callback_token:
            rejection = await validate_acs_request(request, self._callback_token, self._acs_resource_id)
            if rejection is not None:
                logger.warning("ACS callback rejected (auth): status=%s", rejection.status)
                return rejection
        return await self._caller.outbound_call_handler(request)

    async def _acs_incoming(self, request: web.Request) -> web.Response:
        if self._callback_token:
            if request.headers.get("aeg-event-type") != "SubscriptionValidation":
                rejection = await validate_acs_request(request, self._callback_token, self._acs_resource_id)
                if rejection is not None:
                    return rejection
        return await self._caller.inbound_call_handler(request)

    async def _ws_handler_acs(self, request: web.Request) -> web.WebSocketResponse:
        logger.info("ACS media-streaming WebSocket: path=%s", request.path)
        if self._callback_token:
            rejection = await validate_acs_request(request, self._callback_token, self._acs_resource_id)
            if rejection is not None:
                logger.warning("ACS WebSocket rejected (auth): status=%s", rejection.status)
                return rejection  # type: ignore[return-value]
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        logger.info("ACS media stream WebSocket connected (authenticated) path=%s", request.path)
        await self._middleware.forward_messages(ws, is_acs=True)
        return ws

    async def _api_call(self, request: web.Request) -> web.Response:
        body = await request.json()
        number = body.get("number", "").strip()
        prompt = body.get("prompt", "").strip() or None
        opening_message = body.get("opening_message", "").strip() or None

        logger.info("API /voice/call: number=%s, source=%s", number, self._caller.source_number)

        if not number:
            return web.json_response({"status": "error", "message": "Phone number is required"}, status=400)
        if not number.startswith("+"):
            return web.json_response(
                {"status": "error", "message": "Phone number must be in E.164 format (e.g. +49123456789)"},
                status=400,
            )

        self._middleware.set_pending_prompt(prompt, opening_message=opening_message)

        async def _bg_call() -> None:
            try:
                await self._caller.initiate_call(number)
            except Exception as exc:
                self._middleware.set_pending_prompt(None, opening_message=None)
                logger.error("Background call to %s failed: %s", number, exc, exc_info=True)

        asyncio.create_task(_bg_call())
        return web.json_response({"status": "ok", "message": f"Call triggered to {number}"})

    async def _api_status(self, _request: web.Request) -> web.Response:
        return web.json_response({"configured": True, "source_number": self._caller.source_number})
