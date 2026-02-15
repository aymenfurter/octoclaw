"""Core agent -- wraps the GitHub Copilot SDK into a session manager."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from copilot import CopilotClient

from ..config.settings import cfg
from ..sandbox import SandboxExecutor, SandboxToolInterceptor
from ..state.mcp_config import McpConfigStore
from .event_handler import EventHandler
from .one_shot import auto_approve
from .prompt import build_system_prompt
from .tools import get_all_tools

logger = logging.getLogger(__name__)

MAX_START_RETRIES = 3
SESSION_TIMEOUT = 60
RESPONSE_TIMEOUT = 120.0
RETRY_DELAY = 2


class Agent:
    """Manages a CopilotClient + session lifecycle."""

    def __init__(self) -> None:
        self._client: CopilotClient | None = None
        self._session: Any = None
        self.request_counts: dict[str, int] = {}
        self._sandbox: SandboxExecutor | None = None
        self._interceptor: SandboxToolInterceptor | None = None

    def set_sandbox(self, executor: SandboxExecutor) -> None:
        self._sandbox = executor
        self._interceptor = SandboxToolInterceptor(executor)

    @property
    def has_session(self) -> bool:
        return self._session is not None

    async def start(self) -> None:
        cfg.ensure_dirs()
        opts: dict[str, Any] = {"log_level": "error"}
        if cfg.github_token:
            opts["github_token"] = cfg.github_token

        for attempt in range(1, MAX_START_RETRIES + 1):
            try:
                logger.info("[agent.start] attempt %d/%d -- creating CopilotClient", attempt, MAX_START_RETRIES)
                self._client = CopilotClient(opts)
                logger.info("[agent.start] calling client.start() ...")
                await self._client.start()
                logger.info("[agent.start] Copilot CLI started successfully")
                return
            except TimeoutError as exc:
                if attempt < MAX_START_RETRIES:
                    logger.warning("Copilot CLI startup timed out (attempt %d/%d)", attempt, MAX_START_RETRIES)
                    await self._safe_stop_client()
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    raise RuntimeError(
                        f"Could not connect to Copilot CLI after {MAX_START_RETRIES} attempts."
                    ) from exc

    async def stop(self) -> None:
        await self._safe_destroy_session()
        await self._safe_stop_client()

    async def new_session(self) -> Any:
        if not self._client:
            raise RuntimeError("Agent not started")
        logger.info("[agent.new_session] destroying old session ...")
        await self._safe_destroy_session()
        session_cfg = self._build_session_config()
        logger.info(
            "[agent.new_session] creating session: model=%s, tools=%d, mcp_servers=%s",
            session_cfg.get("model"),
            len(session_cfg.get("tools", [])),
            list(session_cfg.get("mcp_servers", {}).keys()) if isinstance(session_cfg.get("mcp_servers"), dict) else "N/A",
        )
        self._session = await self._client.create_session(session_cfg)
        logger.info("[agent.new_session] session created: %s", type(self._session).__name__)
        return self._session

    async def send(
        self,
        prompt: str,
        on_delta: Callable[[str], None] | None = None,
        on_event: Callable[[str, dict], None] | None = None,
    ) -> str | None:
        logger.info("[agent.send] prompt=%r (len=%d), has_session=%s", prompt[:80], len(prompt), self._session is not None)
        if not self._session:
            logger.info("[agent.send] no session -- creating one")
            await self.new_session()

        model = cfg.copilot_model
        self.request_counts[model] = self.request_counts.get(model, 0) + 1

        handler = EventHandler(on_delta, on_event)
        unsub = self._session.on(handler)
        try:
            try:
                logger.info("[agent.send] calling session.send() ...")
                await self._session.send({"prompt": prompt})
                logger.info("[agent.send] session.send() returned, waiting for completion ...")
            except Exception as exc:
                logger.error("[agent.send] session.send() raised: %s", exc, exc_info=True)
                if "Session not found" in str(exc):
                    unsub()
                    logger.info("[agent.send] session expired, creating new session...")
                    await self.new_session()
                    handler = EventHandler(on_delta, on_event)
                    unsub = self._session.on(handler)
                    await self._session.send({"prompt": prompt})
                else:
                    raise
            try:
                await asyncio.wait_for(handler.done.wait(), timeout=RESPONSE_TIMEOUT)
                logger.info("[agent.send] response complete, text_len=%d", len(handler.final_text or ""))
            except TimeoutError:
                logger.warning("[agent.send] response timed out after %ss, partial_len=%d", RESPONSE_TIMEOUT, len(handler.final_text or ""))
                return handler.final_text
        finally:
            unsub()

        if handler.error:
            logger.error("[agent.send] session error: %s", handler.error)
            return None
        return handler.final_text

    async def list_models(self) -> list[dict]:
        if not self._client:
            raise RuntimeError("Agent not started")
        try:
            models = await self._client.list_models()
            return [
                {
                    "id": m.id,
                    "name": m.name,
                    "policy": m.policy.state if m.policy else "enabled",
                    "billing_multiplier": m.billing.multiplier if m.billing else 1.0,
                    "reasoning_efforts": m.supported_reasoning_efforts,
                }
                for m in models
            ]
        except Exception as exc:
            logger.warning("Failed to list models: %s", exc)
            return []

    def _build_session_config(self) -> dict[str, Any]:
        sandbox_active = self._interceptor and self._sandbox and self._sandbox.enabled
        if sandbox_active:
            hooks: dict[str, Any] = {
                "on_pre_tool_use": self._interceptor.on_pre_tool_use,
                "on_post_tool_use": self._interceptor.on_post_tool_use,
            }
        else:
            hooks = {"on_pre_tool_use": auto_approve}

        session_cfg: dict[str, Any] = {
            "model": cfg.copilot_model,
            "streaming": True,
            "tools": get_all_tools(),
            "system_message": {"mode": "replace", "content": build_system_prompt()},
            "hooks": hooks,
            "skill_directories": [str(cfg.builtin_skills_dir), str(cfg.user_skills_dir)],
        }

        if sandbox_active:
            session_cfg["excluded_tools"] = ["create", "view", "edit", "grep", "glob"]

        try:
            session_cfg["mcp_servers"] = McpConfigStore().get_enabled_servers()
        except Exception:
            logger.warning("Failed to load MCP config, using defaults", exc_info=True)
            session_cfg["mcp_servers"] = {
                "playwright": {
                    "type": "local",
                    "command": "npx",
                    "args": ["-y", "@playwright/mcp@latest", "--browser", "chromium", "--headless", "--isolated"],
                    "env": {"PLAYWRIGHT_CHROMIUM_ARGS": "--no-sandbox --disable-setuid-sandbox"},
                    "tools": ["*"],
                },
            }
        return session_cfg

    async def _safe_destroy_session(self) -> None:
        if self._session:
            try:
                await self._session.destroy()
            except Exception:
                logger.debug("Error destroying session", exc_info=True)
            self._session = None

    async def _safe_stop_client(self) -> None:
        if self._client:
            try:
                await self._client.stop()
            except Exception:
                logger.debug("Error stopping client", exc_info=True)
            self._client = None
