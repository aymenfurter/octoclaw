"""Web admin server -- app factory and entry point."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import secrets
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from aiohttp import web
from aiohttp.abc import AbstractAccessLogger
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity, ActivityTypes

from .. import __version__
from ..config.settings import cfg
from ..media import EXTENSION_TO_MIME
from ..messaging.bot import Bot
from ..messaging.proactive import ConversationReferenceStore, send_proactive_message
from ..registries.plugins import get_plugin_registry
from ..state.plugin_config import PluginConfigStore
from ..registries.skills import get_registry as get_skill_registry
from ..sandbox import SandboxExecutor
from ..scheduler import get_scheduler, scheduler_loop
from ..services.azure import AzureCLI
from ..services.deployer import BotDeployer
from ..services.github import GitHubAuth
from ..services.provisioner import Provisioner
from ..services.resource_tracker import ResourceTracker
from ..services.tunnel import CloudflareTunnel
from ..state.deploy_state import DeployStateStore
from ..state.foundry_iq_config import FoundryIQConfigStore
from ..state.infra_config import InfraConfigStore
from ..state.mcp_config import McpConfigStore
from ..state.proactive import get_proactive_store
from ..state.sandbox_config import SandboxConfigStore
from ..state.session_store import SessionStore
from ..util.async_helpers import run_sync
from .bot_endpoint import BotEndpoint
from .chat import ChatHandler
from .routes.env_routes import EnvironmentRoutes
from .routes.foundry_iq_routes import FoundryIQRoutes
from .routes.mcp_routes import McpRoutes
from .routes.plugin_routes import PluginRoutes
from .routes.proactive_routes import ProactiveRoutes
from .routes.profile_routes import ProfileRoutes
from .routes.sandbox_routes import SandboxRoutes
from .routes.scheduler_routes import SchedulerRoutes
from .routes.session_routes import SessionRoutes
from .routes.network_routes import NetworkRoutes
from .routes.skill_routes import SkillRoutes
from .setup import SetupRoutes
from .setup_voice import VoiceSetupRoutes
from .workspace import WorkspaceHandler

logger = logging.getLogger(__name__)

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
_QUIET_PATHS = frozenset({"/api/setup/status", "/health"})


# ---------------------------------------------------------------------------
# Access logger
# ---------------------------------------------------------------------------


class QuietAccessLogger(AbstractAccessLogger):
    """Demotes polling-endpoint log entries to DEBUG."""

    def log(self, request: web.BaseRequest, response: web.StreamResponse, time: float) -> None:
        level = logging.DEBUG if request.path in _QUIET_PATHS else logging.INFO
        self.logger.log(
            level,
            "%s %s %s %s %.3fs",
            request.remote,
            request.method,
            request.path,
            response.status,
            time,
        )


# ---------------------------------------------------------------------------
# Bot Framework adapter
# ---------------------------------------------------------------------------


def create_adapter() -> BotFrameworkAdapter:
    settings = BotFrameworkAdapterSettings(
        app_id=cfg.bot_app_id or None,
        app_password=cfg.bot_app_password or None,
        channel_auth_tenant=cfg.bot_app_tenant_id or None,
    )
    adapter = BotFrameworkAdapter(settings)

    async def on_error(context: TurnContext, error: Exception) -> None:
        logger.error("Bot turn error: %s", error, exc_info=True)
        try:
            activity = Activity(type=ActivityTypes.message, text="An error occurred.")
            if (context.activity.channel_id or "").lower() == "telegram":
                activity.text_format = "plain"
            await context.send_activity(activity)
        except Exception:
            pass

    adapter.on_turn_error = on_error
    return adapter


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

_PUBLIC_PREFIXES = ("/health", "/api/messages", "/acs", "/realtime-acs", "/api/voice/acs-callback", "/api/voice/media-streaming")
_PUBLIC_EXACT = ("/api/auth/check",)

_TUNNEL_ALLOWED_PREFIXES = (
    "/health",
    "/api/messages",
    "/acs",
    "/realtime-acs",
    "/api/voice/acs-callback",
    "/api/voice/media-streaming",
)

_LOCKDOWN_ALLOWED_PREFIXES = (
    "/health",
    "/api/messages",
    "/acs",
    "/realtime-acs",
    "/api/voice/acs-callback",
    "/api/voice/media-streaming",
    "/api/setup/lockdown",
)

_CF_HEADERS = ("cf-connecting-ip", "cf-ray", "cf-ipcountry")


@web.middleware
async def lockdown_middleware(request: web.Request, handler):  # type: ignore[type-arg]
    if not cfg.lockdown_mode:
        return await handler(request)
    if any(request.path.startswith(p) for p in _LOCKDOWN_ALLOWED_PREFIXES):
        return await handler(request)
    return web.json_response(
        {
            "status": "locked",
            "message": (
                "Lock Down Mode is active. The admin panel is disabled. "
                "Use /lockdown off via the bot to restore access."
            ),
        },
        status=403,
    )


@web.middleware
async def tunnel_restriction_middleware(request: web.Request, handler):  # type: ignore[type-arg]
    if not cfg.tunnel_restricted:
        return await handler(request)
    is_tunnel = any(request.headers.get(h) for h in _CF_HEADERS)
    if not is_tunnel:
        return await handler(request)
    if any(request.path.startswith(p) for p in _TUNNEL_ALLOWED_PREFIXES):
        return await handler(request)
    return web.json_response({"status": "forbidden"}, status=403)


@web.middleware
async def auth_middleware(request: web.Request, handler):  # type: ignore[type-arg]
    secret = cfg.admin_secret
    if not secret:
        return await handler(request)

    path = request.path

    # Only protect /api/* endpoints (except public ones); frontend assets are public
    if not path.startswith("/api/"):
        return await handler(request)

    if path in _PUBLIC_EXACT or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
        return await handler(request)

    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {secret}":
        return await handler(request)

    if request.query.get("token") == secret:
        return await handler(request)

    if request.query.get("secret") == secret:
        return await handler(request)

    return web.json_response(
        {"status": "unauthorized", "message": "Invalid or missing admin secret"},
        status=401,
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _append_token(url: str, token: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}token={token}"


async def create_app() -> web.Application:
    factory = AppFactory()
    return await factory.build()


def _create_voice_handler(agent: object, tunnel: object | None = None) -> object | None:
    cfg.reload()
    if not (cfg.acs_connection_string and cfg.acs_source_number and cfg.azure_openai_endpoint):
        logger.info("Voice call not configured (ACS/AOAI settings missing)")
        return None

    from azure.core.credentials import AzureKeyCredential as _AKC

    from ..realtime import AcsCaller, RealtimeMiddleTier, RealtimeRoutes

    def _resolve_acs_urls() -> tuple[str, str]:
        token = cfg.acs_callback_token
        cb_path = cfg.acs_callback_path
        ws_path = cfg.acs_media_streaming_websocket_path

        logger.debug("_resolve_acs_urls: cb_path=%r, ws_path=%r, token=%s", cb_path, ws_path, "set" if token else "empty")

        # If both paths are already absolute URLs, use them directly
        cb_is_absolute = cb_path.startswith("https://")
        ws_is_absolute = ws_path.startswith("wss://")
        if cb_is_absolute and ws_is_absolute:
            resolved = _append_token(cb_path, token), _append_token(ws_path, token)
            logger.info("ACS URLs (absolute): callback=%s, ws=%s", resolved[0], resolved[1])
            return resolved

        # Otherwise, resolve relative paths against the tunnel URL
        tunnel_url = (getattr(tunnel, 'url', None) or "").rstrip("/")
        if tunnel_url:
            cb = cb_path if cb_is_absolute else f"{tunnel_url}{cb_path or '/api/voice/acs-callback'}"
            ws = ws_path if ws_is_absolute else (
                tunnel_url.replace("https://", "wss://").replace("http://", "ws://")
                + (ws_path or "/api/voice/media-streaming")
            )
            resolved = _append_token(cb, token), _append_token(ws, token)
            logger.info("ACS URLs (tunnel): callback=%s, ws=%s", resolved[0], resolved[1])
            return resolved
        logger.warning("ACS URLs fallback to localhost -- calls will fail")
        return (
            cb_path or f"http://localhost:{cfg.admin_port}/api/voice/acs-callback",
            ws_path or f"ws://localhost:{cfg.admin_port}/api/voice/media-streaming",
        )

    caller = AcsCaller(
        source_number=cfg.acs_source_number,
        acs_connection_string=cfg.acs_connection_string,
        resolve_urls=_resolve_acs_urls,
        resolve_source_number=lambda: cfg.acs_source_number,
    )

    realtime_credential: _AKC | object
    if cfg.azure_openai_api_key:
        realtime_credential = _AKC(cfg.azure_openai_api_key)
    else:
        from azure.identity import DefaultAzureCredential as _DAC

        realtime_credential = _DAC()

    rt_middleware = RealtimeMiddleTier(
        endpoint=cfg.azure_openai_endpoint,
        deployment=cfg.azure_openai_realtime_deployment,
        credential=realtime_credential,
        agent=agent,
    )
    handler = RealtimeRoutes(
        caller,
        rt_middleware,
        callback_token=cfg.acs_callback_token,
        acs_resource_id=cfg.acs_resource_id,
    )
    logger.info("Voice call (ACS + Realtime) enabled: source=%s", cfg.acs_source_number)
    return handler


_SCHEDULE_INTERVALS = {"hourly": 3600, "daily": 86400}


class AppFactory:
    """Builds the aiohttp application with all dependencies wired."""

    async def build(self) -> web.Application:
        cfg.ensure_dirs()
        self._ensure_admin_secret()
        await self._init_core()
        self._init_services()
        self._init_voice()

        app = web.Application(
            middlewares=[lockdown_middleware, tunnel_restriction_middleware, auth_middleware],
        )
        app["voice_configured"] = self._voice_routes is not None

        self._register_routes(app)
        self._register_lifecycle(app)
        return app

    @staticmethod
    def _ensure_admin_secret() -> None:
        if not cfg.admin_secret:
            cfg.write_env(ADMIN_SECRET=secrets.token_urlsafe(24))
            logger.info("Generated ADMIN_SECRET (persisted to .env)")

    async def _init_core(self) -> None:
        from ..agent.agent import Agent

        logger.info("[init_core] creating Agent ...")
        self._agent = Agent()
        logger.info("[init_core] starting Agent (Copilot CLI) ...")
        await self._agent.start()
        logger.info("[init_core] Agent started successfully")

        self._adapter = create_adapter()
        self._conv_store = ConversationReferenceStore()
        self._session_store = SessionStore()

        self._bot = Bot(self._agent, self._conv_store)
        self._bot.session_store = self._session_store
        self._bot.adapter = self._adapter
        self._bot_ep = BotEndpoint(self._adapter, self._bot)
        logger.info("[init_core] core initialization complete")

    def _init_services(self) -> None:
        self._az = AzureCLI()
        self._gh = GitHubAuth()
        self._tunnel = CloudflareTunnel()
        self._deploy_store = DeployStateStore()
        self._deployer = BotDeployer(self._az, self._deploy_store)
        self._scheduler = get_scheduler()
        self._proactive_store = get_proactive_store()
        self._infra_store = InfraConfigStore()
        self._mcp_store = McpConfigStore()
        self._sandbox_store = SandboxConfigStore()
        self._sandbox_executor = SandboxExecutor(self._sandbox_store)
        self._agent.set_sandbox(self._sandbox_executor)
        self._foundry_iq_store = FoundryIQConfigStore()
        self._provisioner = Provisioner(
            self._az, self._deployer, self._tunnel,
            self._infra_store, self._deploy_store,
        )

    def _init_voice(self) -> None:
        self._voice_routes = _create_voice_handler(self._agent, self._tunnel)

    def _rebuild_adapter(self) -> BotFrameworkAdapter:
        cfg.reload()
        self._adapter = create_adapter()
        self._bot_ep.adapter = self._adapter
        self._bot.adapter = self._adapter
        logger.info(
            "Adapter rebuilt: app_id=%s, tenant=%s, password=%s",
            (cfg.bot_app_id[:12] + "...") if cfg.bot_app_id else "(none)",
            (cfg.bot_app_tenant_id[:12] + "...") if cfg.bot_app_tenant_id else "(none)",
            "set" if cfg.bot_app_password else "MISSING",
        )
        return self._adapter

    # ------------------------------------------------------------------
    # Route registration
    # ------------------------------------------------------------------

    def _register_routes(self, app: web.Application) -> None:
        router = app.router

        async def auth_check(req: web.Request) -> web.Response:
            auth = req.headers.get("Authorization", "")
            ok = auth == f"Bearer {cfg.admin_secret}"
            return web.json_response({"authenticated": ok})

        router.add_post("/api/auth/check", auth_check)

        SetupRoutes(
            self._az, self._gh, self._tunnel, self._deployer,
            self._rebuild_adapter, self._infra_store,
            self._provisioner, self._deploy_store,
        ).register(router)

        VoiceSetupRoutes(self._az, self._infra_store).register(router)

        ChatHandler(
            self._agent,
            session_store=self._session_store,
            sandbox_interceptor=self._sandbox_executor,
        ).register(router)

        WorkspaceHandler().register(router)
        self._bot_ep.register(router)
        self._register_voice_dynamic(app)

        SchedulerRoutes(self._scheduler).register(router)
        SessionRoutes(self._session_store).register(router)
        SkillRoutes(get_skill_registry()).register(router)
        McpRoutes(self._mcp_store).register(router)
        PluginRoutes(get_plugin_registry(), PluginConfigStore()).register(router)
        ProfileRoutes().register(router)
        ProactiveRoutes(
            self._proactive_store,
            adapter=self._adapter,
            conv_store=self._conv_store,
            app_id=cfg.bot_app_id,
        ).register(router)
        EnvironmentRoutes(self._deploy_store, self._az).register(router)
        SandboxRoutes(
            self._sandbox_store, self._sandbox_executor, self._az, self._deploy_store,
        ).register(router)
        FoundryIQRoutes(self._foundry_iq_store, self._az, self._deploy_store).register(router)
        NetworkRoutes(self._tunnel, self._az, self._sandbox_store, self._foundry_iq_store).register(router)

        router.add_get("/api/media/{filename:.+}", _serve_media)
        router.add_get("/health", _health)

        # Frontend SPA from app/frontend/dist/
        fe = _FRONTEND_DIR
        if fe.exists():
            router.add_get("/", _serve_index)
            if (fe / "assets").is_dir():
                router.add_static("/assets/", path=str(fe / "assets"), name="fe_assets")
            for fname in ("favicon.ico", "logo.png", "headertext.png"):
                fpath = fe / fname
                if fpath.exists():
                    router.add_get(f"/{fname}", _make_file_handler(fpath))
            # SPA catch-all: serve index.html for client-side routes
            # (skip /api/* paths so unregistered API calls get a proper 404)
            router.add_get("/{tail:[^/].*}", _serve_spa_or_404)

    def _register_voice_dynamic(self, app: web.Application) -> None:
        app["_voice_handler"] = self._voice_routes
        agent = self._agent

        def reinit_voice() -> None:
            handler = _create_voice_handler(agent, self._tunnel)
            app["_voice_handler"] = handler
            app["voice_configured"] = handler is not None

        app["_reinit_voice"] = reinit_voice

        def _not_configured() -> web.Response:
            return web.json_response(
                {
                    "status": "error",
                    "message": (
                        "Voice calling is not configured. Deploy ACS + "
                        "Azure OpenAI resources in the Voice Call section first."
                    ),
                },
                status=400,
            )

        async def voice_call(req: web.Request) -> web.Response:
            h = req.app["_voice_handler"]
            return _not_configured() if h is None else await h._api_call(req)

        async def voice_status(req: web.Request) -> web.Response:
            h = req.app["_voice_handler"]
            return _not_configured() if h is None else await h._api_status(req)

        async def acs_callback(req: web.Request) -> web.Response:
            h = req.app["_voice_handler"]
            logger.info("ACS callback hit: method=%s path=%s handler=%s", req.method, req.path, "configured" if h else "NONE")
            return _not_configured() if h is None else await h._acs_callback(req)

        async def acs_incoming(req: web.Request) -> web.Response:
            h = req.app["_voice_handler"]
            logger.info("ACS incoming hit: method=%s path=%s handler=%s", req.method, req.path, "configured" if h else "NONE")
            return _not_configured() if h is None else await h._acs_incoming(req)

        async def ws_handler_acs(req: web.Request) -> web.WebSocketResponse:
            h = req.app["_voice_handler"]
            logger.info("ACS media-streaming WS hit: method=%s path=%s handler=%s", req.method, req.path, "configured" if h else "NONE")
            return _not_configured() if h is None else await h._ws_handler_acs(req)  # type: ignore[return-value]

        router = app.router
        router.add_post("/api/voice/call", voice_call)
        router.add_get("/api/voice/status", voice_status)
        # Legacy routes (kept for backwards compat)
        router.add_post("/acs", acs_callback)
        router.add_post("/acs/incoming", acs_incoming)
        router.add_get("/realtime-acs", ws_handler_acs)
        # Routes matching cfg.acs_callback_path / cfg.acs_media_streaming_websocket_path
        router.add_post("/api/voice/acs-callback", acs_callback)
        router.add_post("/api/voice/acs-callback/incoming", acs_incoming)
        router.add_get("/api/voice/media-streaming", ws_handler_acs)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _make_notify(self) -> Callable[[str], Awaitable[bool]]:
        async def notify(message: str) -> bool:
            return await send_proactive_message(
                self._adapter, self._conv_store, cfg.bot_app_id, message,
            )

        return notify

    def _register_lifecycle(self, app: web.Application) -> None:
        async def notify(message: str) -> None:
            await send_proactive_message(
                self._adapter, self._conv_store, cfg.bot_app_id, message,
            )

        self._scheduler.set_notify_callback(notify)
        app.on_startup.append(self._on_startup)
        app.on_cleanup.append(self._on_cleanup)

    async def _on_startup(self, app: web.Application) -> None:
        from ..proactive_loop import proactive_delivery_loop

        self._rebuild_adapter()

        app["scheduler_task"] = asyncio.create_task(scheduler_loop())
        app["proactive_task"] = asyncio.create_task(
            proactive_delivery_loop(self._make_notify(), session_store=self._session_store),
        )
        app["foundry_iq_task"] = asyncio.create_task(
            _foundry_iq_index_loop(self._foundry_iq_store),
        )
        app["reconcile_task"] = asyncio.create_task(self._reconcile_deployments())

        if cfg.lockdown_mode:
            logger.info("Lock Down Mode active -- skipping infrastructure provisioning")
            return

        if not self._infra_store.bot_configured:
            return

        # Provision order: 1) start tunnel → 2) create/update bot with new URL
        logger.info("Startup: provisioning infrastructure from config ...")
        steps = await run_sync(self._provisioner.provision)
        self._rebuild_adapter()
        for s in steps:
            logger.info("  provision: %s = %s (%s)", s.get("step"), s.get("status"), s.get("detail", ""))

        # Safety net: always force-sync the bot endpoint to the live tunnel URL
        await self._sync_bot_endpoint()

    async def _sync_bot_endpoint(self) -> None:
        """Ensure the Azure Bot Service endpoint matches the current tunnel URL."""
        tunnel_url = self._tunnel.url
        bot_name = cfg.env.read("BOT_NAME")
        if not (tunnel_url and bot_name):
            return
        endpoint = tunnel_url.rstrip("/") + "/api/messages"
        logger.info("Endpoint sync: updating bot '%s' to %s", bot_name, endpoint)
        try:
            ok, msg = await run_sync(self._az.update_endpoint, endpoint)
            if ok:
                logger.info("Endpoint sync: OK — %s", msg)
            else:
                logger.warning("Endpoint sync: FAILED — %s", msg)
        except Exception as exc:
            logger.warning("Endpoint sync: error — %s", exc)

    async def _reconcile_deployments(self) -> None:
        try:
            tracker = ResourceTracker(self._az, self._deploy_store)
            cleaned = await run_sync(tracker.reconcile)
            if cleaned:
                logger.info(
                    "Startup reconcile: removed %d stale deployment(s): %s",
                    len(cleaned), ", ".join(c["deploy_id"] for c in cleaned),
                )
        except Exception as exc:
            logger.warning("Startup reconcile failed (non-fatal): %s", exc)

    async def _on_cleanup(self, _app: web.Application) -> None:
        for key in ("scheduler_task", "proactive_task", "foundry_iq_task", "reconcile_task"):
            task = _app.get(key)
            if task and not task.done():
                task.cancel()

        if cfg.lockdown_mode:
            logger.info("Lock Down Mode active -- skipping shutdown decommission")
        elif self._infra_store.bot_configured and cfg.env.read("BOT_NAME"):
            logger.info("Shutdown: decommissioning infrastructure ...")
            steps = await run_sync(self._provisioner.decommission)
            for s in steps:
                logger.info("  decommission: %s = %s (%s)", s.get("step"), s.get("status"), s.get("detail", ""))

        await self._agent.stop()


# ---------------------------------------------------------------------------
# Utility handlers
# ---------------------------------------------------------------------------


async def _foundry_iq_index_loop(store: FoundryIQConfigStore) -> None:
    from ..services.foundry_iq import index_memories

    await asyncio.sleep(60)
    while True:
        try:
            store._load()
            schedule = store.config.index_schedule
            if store.enabled and store.is_configured and schedule in _SCHEDULE_INTERVALS:
                logger.info("Foundry IQ: running scheduled indexing (%s)...", schedule)
                result = await run_sync(index_memories, store)
                logger.info("Foundry IQ indexing: %s (indexed=%s)", result.get("status"), result.get("indexed", 0))
            interval = _SCHEDULE_INTERVALS.get(schedule, 86400)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error("Foundry IQ index loop error: %s", exc, exc_info=True)
            interval = 3600
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return


async def _serve_media(req: web.Request) -> web.Response:
    filename = req.match_info["filename"]
    if ".." in filename or filename.startswith("/"):
        return web.Response(status=403, text="Forbidden")
    file_path = cfg.media_outgoing_sent_dir / filename
    if not file_path.is_file():
        return web.Response(status=404, text="Not found")
    content_type = (
        EXTENSION_TO_MIME.get(file_path.suffix.lower())
        or mimetypes.guess_type(file_path.name)[0]
        or "application/octet-stream"
    )
    return web.FileResponse(file_path, headers={"Content-Type": content_type})


async def _health(_req: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "version": __version__})


def _make_file_handler(fpath: Path):
    async def handler(_req: web.Request) -> web.Response:
        ct = mimetypes.guess_type(fpath.name)[0] or "application/octet-stream"
        return web.FileResponse(fpath, headers={"Content-Type": ct})
    return handler


async def _serve_index(req: web.Request) -> web.Response:
    index = _FRONTEND_DIR / "index.html"
    if not index.exists():
        return web.Response(status=404, text="Not found")
    html = index.read_text()
    return web.Response(
        text=html,
        content_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


async def _serve_spa_or_404(req: web.Request) -> web.Response:
    """SPA catch-all that skips /api/* paths (return 404 for unregistered API routes)."""
    if req.path.startswith("/api/"):
        return web.json_response(
            {"status": "error", "message": f"Unknown endpoint: {req.method} {req.path}"},
            status=404,
        )
    return await _serve_index(req)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    )
    port = cfg.admin_port
    logger.info("Starting admin server on port %d ...", port)

    cfg.reload()
    if not cfg.admin_secret:
        cfg.write_env(ADMIN_SECRET=secrets.token_urlsafe(24))
        logger.info("Generated ADMIN_SECRET (persisted to .env)")

    logger.info("Admin UI: http://localhost:%d/?secret=%s", port, cfg.admin_secret)
    web.run_app(create_app(), host="0.0.0.0", port=port, access_log_class=QuietAccessLogger)


if __name__ == "__main__":
    main()
