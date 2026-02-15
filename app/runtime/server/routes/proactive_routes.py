"""Proactive messaging API routes -- /api/proactive/*."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web

from ...state.proactive import ProactiveStore

if TYPE_CHECKING:
    from botbuilder.core import BotFrameworkAdapter

    from ...messaging.proactive import ConversationReferenceStore

logger = logging.getLogger(__name__)


class ProactiveRoutes:
    """REST endpoints for proactive follow-up management."""

    def __init__(
        self,
        store: ProactiveStore,
        adapter: BotFrameworkAdapter | None = None,
        conv_store: ConversationReferenceStore | None = None,
        app_id: str = "",
    ) -> None:
        self._store = store
        self._adapter = adapter
        self._conv_store = conv_store
        self._app_id = app_id

    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get("/api/proactive", self.get_state)
        router.add_put("/api/proactive/enabled", self.set_enabled)
        router.add_delete("/api/proactive/pending", self.cancel_pending)
        router.add_put("/api/proactive/preferences", self.update_preferences)
        router.add_post("/api/proactive/reaction", self.record_reaction)
        router.add_post("/api/proactive/dry-run", self.dry_run)
        router.add_post("/api/proactive/memory/form", self.force_memory)

    async def get_state(self, _req: web.Request) -> web.Response:
        from ...state.memory import get_memory

        state = self._store.get_full_state()
        state["memory"] = get_memory().get_status()
        state["conversation_refs"] = self._conv_store.count if self._conv_store else 0
        return web.json_response(state)

    async def set_enabled(self, req: web.Request) -> web.Response:
        data = await req.json()
        enabled = bool(data.get("enabled", False))
        self._store.enabled = enabled
        logger.info("Proactive messaging %s", "enabled" if enabled else "disabled")
        return web.json_response({"enabled": enabled})

    async def cancel_pending(self, _req: web.Request) -> web.Response:
        cancelled = self._store.clear_pending()
        if cancelled:
            return web.json_response({
                "status": "cancelled",
                "message": cancelled.message[:80],
            })
        return web.json_response({"status": "none", "message": "No pending follow-up."})

    async def update_preferences(self, req: web.Request) -> web.Response:
        data = await req.json()
        allowed = {"min_gap_hours", "max_daily", "avoided_topics", "preferred_times"}
        updates = {k: v for k, v in data.items() if k in allowed}
        if updates:
            self._store.update_preferences(**updates)
        return web.json_response(self._store.get_full_state()["preferences"])

    async def record_reaction(self, req: web.Request) -> web.Response:
        data = await req.json()
        reaction = data.get("reaction", "neutral")
        detail = data.get("detail", "")

        msg_id = data.get("id")
        if msg_id:
            ok = self._store.update_reaction(msg_id, reaction, detail)
        else:
            ok = self._store.mark_latest_reaction(reaction, detail)

        if ok:
            if reaction == "negative" and detail:
                prefs = self._store.preferences
                if detail not in prefs.avoided_topics:
                    avoided = prefs.avoided_topics + [detail]
                    self._store.update_preferences(avoided_topics=avoided)
            return web.json_response({"status": "recorded", "reaction": reaction})
        return web.json_response({"status": "not_found"}, status=404)

    async def force_memory(self, _req: web.Request) -> web.Response:
        """Manually trigger memory formation without waiting for idle timer."""
        from ...state.memory import get_memory

        mem = get_memory()
        result = await mem.force_form()
        status_code = 200 if result["status"] == "ok" else 409 if result["status"] == "already_running" else 422
        return web.json_response(result, status=status_code)

    async def dry_run(self, _req: web.Request) -> web.Response:
        if self._adapter is None or self._conv_store is None:
            return web.json_response(
                {"status": "error", "message": "Delivery not configured."},
                status=500,
            )

        refs = self._conv_store.get_all()
        if not refs:
            return web.json_response({
                "status": "error",
                "message": "No conversation references stored.",
                "conversation_refs": 0,
            })

        test_message = (
            "[dry-run] This is a proactive delivery test. "
            "If you see this, delivery is working!"
        )

        results: list[dict[str, Any]] = []
        for ref in refs:
            ref_key = (
                f"{ref.channel_id}:{ref.user.id}"
                if ref.user else ref.channel_id or "unknown"
            )
            send_ok = [True]
            error_msg = [""]

            async def _callback(
                turn_context: Any,
                _msg: str = test_message,
                _ch: str = (ref.channel_id or "").lower(),
                _ok: list = send_ok,
                _err: list = error_msg,
            ) -> None:
                from botbuilder.schema import Activity
                from botbuilder.schema import ActivityTypes as AT

                activity = Activity(type=AT.message, text=_msg)
                if _ch == "telegram":
                    from ...messaging.formatting import strip_markdown
                    activity.text = strip_markdown(_msg)
                    activity.text_format = "plain"
                try:
                    await turn_context.send_activity(activity)
                except Exception as exc:
                    _ok[0] = False
                    _err[0] = str(exc)

            try:
                effective_bot_id = (
                    self._app_id
                    or (ref.bot.id if ref.bot else None)
                    or ""
                )
                await self._adapter.continue_conversation(
                    ref, _callback, bot_id=effective_bot_id
                )
                results.append({
                    "ref": ref_key,
                    "channel": ref.channel_id,
                    "ok": send_ok[0],
                    "error": error_msg[0] or None,
                })
            except Exception as exc:
                results.append({
                    "ref": ref_key,
                    "channel": ref.channel_id,
                    "ok": False,
                    "error": str(exc),
                })

        all_ok = all(r["ok"] for r in results)
        return web.json_response({
            "status": "ok" if all_ok else "partial",
            "message": (
                f"Test message sent to {len(results)} channel(s)."
                if all_ok
                else (
                    f"{sum(1 for r in results if r['ok'])}"
                    f"/{len(results)} channel(s) succeeded."
                )
            ),
            "conversation_refs": len(refs),
            "results": results,
        })
