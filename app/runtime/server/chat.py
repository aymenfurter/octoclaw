"""WebSocket chat handler -- /api/chat/ws."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import web

from ..config.settings import cfg
from ..media.outgoing import collect_pending_outgoing
from ..messaging.cards import attachment_to_dict, drain_pending_cards
from ..messaging.commands import CommandDispatcher
from ..state.memory import get_memory
from ..state.session_store import SessionStore

if TYPE_CHECKING:
    from ..agent.agent import Agent
    from ..sandbox import SandboxToolInterceptor

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class ChatHandler:
    """WebSocket handler for the admin chat interface."""

    def __init__(
        self,
        agent: Agent,
        session_store: SessionStore,
        sandbox_interceptor: SandboxToolInterceptor | None = None,
    ) -> None:
        self._agent = agent
        self._sessions = session_store
        self._sandbox = sandbox_interceptor
        self._commands = CommandDispatcher(agent, session_store=session_store)
        self._suggestions = self._load_suggestions()

    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get("/api/chat/ws", self.handle)
        router.add_get("/api/models", self.list_models)
        router.add_get("/api/chat/models", self.list_models)
        router.add_get("/api/chat/suggestions", self.get_suggestions)

    async def handle(self, req: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(req)
        logger.info("[chat.handle] WebSocket connected from %s", req.remote)

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                logger.debug("[chat.handle] received: %s", msg.data[:200])
                try:
                    data = json.loads(msg.data)
                    await self._dispatch(ws, data)
                except json.JSONDecodeError:
                    logger.warning("[chat.handle] invalid JSON: %s", msg.data[:100])
                    await ws.send_json({"type": "error", "content": "Invalid JSON"})
                except Exception:
                    logger.exception("[chat.handle] unhandled error in dispatch")
                    await ws.send_json({"type": "error", "content": "Internal error"})
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("[chat.handle] WebSocket error: %s", ws.exception())

        logger.info("[chat.handle] WebSocket disconnected")
        return ws

    async def list_models(self, _req: web.Request) -> web.Response:
        try:
            models = await self._agent.list_models()
        except Exception:
            models = []
        return web.json_response({
            "models": models,
            "current": cfg.copilot_model,
        })

    async def get_suggestions(self, _req: web.Request) -> web.Response:
        return web.json_response({"suggestions": self._suggestions})

    async def _dispatch(self, ws: web.WebSocketResponse, data: dict) -> None:
        action = data.get("action", "")
        logger.info("[chat.dispatch] action=%s keys=%s", action, list(data.keys()))
        if action == "new_session":
            await self._agent.new_session()
            session_id = str(uuid.uuid4())
            logger.info("[chat.dispatch] new session created: %s", session_id)
            self._sessions.start_session(session_id, model=cfg.copilot_model)
            await ws.send_json({"type": "session_created", "session_id": session_id})
        elif action == "resume_session":
            await self._resume_session(ws, data.get("session_id", ""))
        elif action == "send":
            await self._send_prompt(ws, data)
        else:
            logger.warning("[chat.dispatch] unknown action: %s", action)
            await ws.send_json({"type": "error", "content": f"Unknown action: {action}"})

    async def _send_prompt(self, ws: web.WebSocketResponse, data: dict) -> None:
        text = (data.get("text") or data.get("message") or "").strip()
        if not text:
            logger.debug("[chat.send_prompt] empty text, ignoring")
            return

        session_id = data.get("session_id", "")
        logger.info("[chat.send_prompt] text=%r session=%s", text[:80], session_id or "(none)")

        # Ensure session store tracks a session -- auto-create one if none is
        # active so that messages are always persisted to disk.
        if session_id and self._sessions.current_session_id != session_id:
            self._sessions.start_session(session_id)
        elif not self._sessions.current_session_id:
            auto_id = str(uuid.uuid4())
            logger.info("[chat.send_prompt] no active session, auto-creating %s", auto_id)
            self._sessions.start_session(auto_id, model=cfg.copilot_model)

        # Slash command dispatch
        if text.startswith("/"):
            handled = await self._try_command(ws, text, session_id)
            if handled:
                logger.info("[chat.send_prompt] handled as command")
                return

        self._sessions.record("user", text)
        memory = get_memory()
        memory.record("user", text)

        chunks: list[str] = []

        async def on_delta(delta: str) -> None:
            chunks.append(delta)
            await ws.send_json({"type": "delta", "content": delta})

        async def on_event(event: dict[str, Any]) -> None:
            event_type = event.pop("type", "")
            if event_type == "sandbox_exec" and self._sandbox:
                result = await self._sandbox.intercept({"type": event_type, **event})
                if result:
                    await ws.send_json({"type": "sandbox_result", **result})
            await ws.send_json({"type": "event", "event": event_type, **event})

        logger.info("[chat.send_prompt] calling agent.send() ...")
        try:
            response = await self._agent.send(
                text,
                on_delta=lambda d: asyncio.ensure_future(on_delta(d)),
                on_event=lambda t, d: asyncio.ensure_future(on_event({"type": t, **d})),
            )
        except Exception:
            logger.exception("[chat.send_prompt] agent.send() raised")
            await ws.send_json({"type": "error", "content": "Agent error -- check server logs"})
            return
        full_text = "".join(chunks) or response or ""
        logger.info("[chat.send_prompt] response complete, len=%d, chunks=%d", len(full_text), len(chunks))

        self._sessions.record("assistant", full_text)
        memory.record("assistant", full_text)

        outgoing = collect_pending_outgoing()
        cards = drain_pending_cards()

        if outgoing:
            await ws.send_json({"type": "media", "files": outgoing})
        if cards:
            await ws.send_json({"type": "cards", "cards": [attachment_to_dict(c) for c in cards]})
        await ws.send_json({"type": "done"})

    async def _try_command(
        self, ws: web.WebSocketResponse, text: str, session_id: str
    ) -> bool:
        if not text.startswith("/"):
            return False

        async def reply(content: str) -> None:
            await ws.send_json({"type": "message", "content": content})
            await ws.send_json({"type": "done"})

        return await self._commands.try_handle(text, reply, channel="web")

    async def _resume_session(
        self, ws: web.WebSocketResponse, session_id: str
    ) -> None:
        session = self._sessions.get_session(session_id)
        if not session:
            await ws.send_json({
                "type": "error",
                "content": f"Session {session_id} not found",
            })
            return

        messages = session.get("messages", [])
        resume_tpl = _TEMPLATES_DIR / "session_resume_prompt.md"
        if resume_tpl.exists():
            context = "\n".join(
                f"[{m['role']}] {m['content']}" for m in messages[-20:]
            )
            prompt = resume_tpl.read_text().replace("{{context}}", context)
            await self._agent.send(prompt)

        # Point session store at this session for continued recording
        self._sessions.start_session(session_id)

        await ws.send_json({
            "type": "session_resumed",
            "session_id": session_id,
            "message_count": len(messages),
        })

    @staticmethod
    def _load_suggestions() -> list[str]:
        path = cfg.data_dir / "suggestions.txt"
        if not path.exists():
            return []
        return [
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
