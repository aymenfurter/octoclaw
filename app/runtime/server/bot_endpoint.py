"""Bot Framework endpoint -- POST /api/messages."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web
from botbuilder.schema import Activity

from ..config.settings import cfg

if TYPE_CHECKING:
    from botbuilder.core import BotFrameworkAdapter

    from ..messaging.bot import Bot

logger = logging.getLogger(__name__)


class BotEndpoint:
    """Handles incoming Bot Framework activities."""

    def __init__(self, adapter: BotFrameworkAdapter, bot: Bot) -> None:
        self.adapter = adapter
        self._bot = bot

    def register(self, router: web.UrlDispatcher) -> None:
        router.add_post("/api/messages", self.handle)
        router.add_get("/api/messages", self._get_messages)

    async def _get_messages(self, _req: web.Request) -> web.Response:
        """GET /api/messages -- simple health probe for the bot endpoint."""
        return web.json_response({
            "status": "ok",
            "endpoint": "/api/messages",
            "method": "POST required",
            "bot_configured": bool(cfg.bot_app_id),
        })

    async def handle(self, req: web.Request) -> web.Response:
        logger.info(
            "[bot] POST /api/messages from %s | content-type=%s content-length=%s",
            req.remote,
            req.headers.get("Content-Type", "?"),
            req.headers.get("Content-Length", "?"),
        )
        logger.debug(
            "[bot] Request headers: %s",
            {k: (v[:40] + "..." if len(v) > 40 else v) for k, v in req.headers.items()},
        )

        if not cfg.bot_app_id or not cfg.bot_app_password:
            logger.warning(
                "[bot] Rejected: bot credentials not configured "
                "(app_id=%s, password=%s)",
                bool(cfg.bot_app_id), bool(cfg.bot_app_password),
            )
            return web.json_response(
                {"status": "error", "message": "Bot credentials not configured"},
                status=503,
            )

        try:
            raw_body = await req.read()
            logger.info("[bot] Raw body length: %d bytes", len(raw_body))
        except Exception as exc:
            logger.error("[bot] Failed to read request body: %s", exc)
            return web.json_response(
                {"status": "error", "message": "Failed to read request body"},
                status=400,
            )

        try:
            import json as _json
            body = _json.loads(raw_body)
        except Exception as exc:
            logger.error(
                "[bot] Failed to parse JSON body: %s | raw=%s",
                exc, raw_body[:500],
            )
            return web.json_response(
                {"status": "error", "message": f"Invalid JSON: {exc}"},
                status=400,
            )

        channel = body.get("channelId", "?")
        activity_type = body.get("type", "?")
        from_id = body.get("from", {}).get("id", "?")
        service_url = body.get("serviceUrl", "?")
        auth_header = req.headers.get("Authorization", "")

        logger.info(
            "[bot] Activity: type=%s channel=%s from=%s serviceUrl=%s auth=%s",
            activity_type,
            channel,
            from_id,
            service_url,
            ("Bearer " + auth_header[7:19] + "...") if auth_header.startswith("Bearer ") else repr(auth_header[:20]),
        )
        logger.info(
            "[bot] Adapter config: app_id=%s tenant=%s password=%s",
            (cfg.bot_app_id[:12] + "...") if cfg.bot_app_id else "(none)",
            (cfg.bot_app_tenant_id[:12] + "...") if cfg.bot_app_tenant_id else "(none)",
            "set" if cfg.bot_app_password else "MISSING",
        )

        try:
            activity = Activity().deserialize(body)
            response = await self.adapter.process_activity(
                activity, auth_header, self._bot.on_turn
            )
            if response:
                logger.info(
                    "[bot] Adapter returned response: status=%s body_len=%d",
                    response.status, len(response.body) if response.body else 0,
                )
                return web.Response(
                    status=response.status,
                    body=response.body,
                    content_type="application/json",
                )
            logger.info("[bot] Activity processed successfully (200)")
            return web.Response(status=200)
        except PermissionError as exc:
            logger.warning("[bot] Authentication failed (401): %s", exc)
            return web.Response(status=401, text=str(exc))
        except Exception as exc:
            logger.exception(
                "[bot] Error processing activity: %s (type=%s channel=%s from=%s)",
                exc, activity_type, channel, from_id,
            )
            return web.json_response(
                {"status": "error", "message": f"Processing failed: {exc}"},
                status=500,
            )
