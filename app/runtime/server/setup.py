"""Setup API routes -- /api/setup/*."""

from __future__ import annotations

import logging
from collections.abc import Callable

from aiohttp import web

from ..config.settings import SECRET_ENV_KEYS, cfg
from ..services.azure import AzureCLI
from ..services.deployer import BotDeployer
from ..services.github import GitHubAuth
from ..services.provisioner import Provisioner
from ..services.tunnel import CloudflareTunnel
from ..state.deploy_state import DeployStateStore
from ..state.infra_config import InfraConfigStore
from ..util.async_helpers import run_sync
from .setup_preflight import PreflightRoutes
from .setup_prerequisites import PrerequisitesRoutes
from .setup_voice import VoiceSetupRoutes
from .smoke_test import SmokeTestRunner

logger = logging.getLogger(__name__)


class SetupRoutes:
    """All /api/setup/* route handlers."""

    def __init__(
        self,
        az: AzureCLI,
        gh: GitHubAuth,
        tunnel: CloudflareTunnel,
        deployer: BotDeployer,
        rebuild_adapter: Callable,
        infra_store: InfraConfigStore,
        provisioner: Provisioner,
        deploy_store: DeployStateStore | None = None,
    ) -> None:
        self._az = az
        self._gh = gh
        self._tunnel = tunnel
        self._deployer = deployer
        self._rebuild = rebuild_adapter
        self._store = infra_store
        self._provisioner = provisioner
        self._deploy_store = deploy_store
        self._voice_routes = VoiceSetupRoutes(az, infra_store)
        self._prerequisites_routes = PrerequisitesRoutes(az, infra_store, deploy_store)
        self._preflight_routes = PreflightRoutes(tunnel, infra_store)

    def register(self, router: web.UrlDispatcher) -> None:
        r = router
        r.add_get("/api/setup/status", self.status)
        r.add_post("/api/setup/azure/login", self.azure_login)
        r.add_get("/api/setup/azure/check", self.azure_check)
        r.add_post("/api/setup/azure/logout", self.azure_logout)
        r.add_get("/api/setup/azure/subscriptions", self.list_subscriptions)
        r.add_post("/api/setup/azure/subscription", self.set_subscription)
        r.add_get("/api/setup/azure/resource-groups", self.list_resource_groups)
        r.add_get("/api/setup/copilot/status", self.copilot_status)
        r.add_post("/api/setup/copilot/login", self.copilot_login)
        r.add_post("/api/setup/copilot/token", self.copilot_set_token)
        r.add_post("/api/setup/copilot/smoke-test", self.smoke_test)
        r.add_post("/api/setup/tunnel/start", self.start_tunnel)
        r.add_post("/api/setup/tunnel/stop", self.stop_tunnel)
        r.add_post("/api/setup/tunnel/restrict", self.toggle_tunnel_restriction)
        r.add_get("/api/setup/bot/config", self.get_bot_config)
        r.add_post("/api/setup/bot/config", self.save_bot_config)
        r.add_get("/api/setup/channels/config", self.get_channels_config)
        r.add_post("/api/setup/channels/telegram/config", self.save_telegram_config)
        r.add_post("/api/setup/channels/telegram/remove", self.remove_telegram_config)
        r.add_post("/api/setup/configuration/save", self.save_configuration)
        r.add_get("/api/setup/infra/status", self.infra_status)
        r.add_post("/api/setup/infra/deploy", self.infra_deploy)
        r.add_post("/api/setup/infra/decommission", self.infra_decommission)
        self._prerequisites_routes.register(r)
        self._voice_routes.register(r)
        r.add_get("/api/setup/config", self.get_config)
        r.add_post("/api/setup/config", self.save_config)
        self._preflight_routes.register(r)
        r.add_get("/api/setup/lockdown", self.lockdown_status)
        r.add_post("/api/setup/lockdown", self.lockdown_toggle)

    # -- Status --

    async def status(self, _req: web.Request) -> web.Response:
        account = self._az.account_info()
        copilot = self._gh.status()
        kv_url = cfg.env.read("KEY_VAULT_URL") or ""

        return web.json_response({
            "azure": {
                "logged_in": account is not None,
                "user": account.get("user", {}).get("name") if account else None,
                "subscription": account.get("name") if account else None,
                "subscription_id": account.get("id") if account else None,
            },
            "copilot": copilot,
            "tunnel": {
                "active": self._tunnel.is_active,
                "url": self._tunnel.url,
                "restricted": cfg.tunnel_restricted,
            },
            "lockdown_mode": cfg.lockdown_mode,
            "prerequisites_configured": bool(kv_url),
            "bot_configured": self._store.bot_configured,
            "bot_deployed": bool(cfg.env.read("BOT_NAME")),
            "telegram_configured": self._store.telegram_configured,
            "voice_call_configured": self._store.voice_call_configured,
            "model": cfg.copilot_model,
            "env_path": str(cfg.env.path),
            "data_dir": str(cfg.data_dir),
        })

    # -- Azure --

    async def azure_login(self, _req: web.Request) -> web.Response:
        account = self._az.account_info()
        if account:
            return web.json_response({
                "status": "already_logged_in",
                "user": account.get("user", {}).get("name"),
                "subscription": account.get("name"),
            })
        info = self._az.login_device_code()
        return web.json_response({"status": "device_code_pending", **info})

    async def azure_check(self, _req: web.Request) -> web.Response:
        account = self._az.account_info()
        if account:
            return web.json_response({
                "status": "logged_in",
                "user": account.get("user", {}).get("name"),
                "subscription": account.get("name"),
            })
        return web.json_response({"status": "pending"})

    async def azure_logout(self, _req: web.Request) -> web.Response:
        ok, msg = self._az.ok("logout")
        self._az.invalidate_cache("account", "show")
        return _ok(msg) if ok else _error(msg)

    async def list_subscriptions(self, _req: web.Request) -> web.Response:
        subs = self._az.json("account", "list") or []
        return web.json_response([
            {
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "is_default": s.get("isDefault", False),
                "state": s.get("state", ""),
            }
            for s in (subs if isinstance(subs, list) else [])
        ])

    async def set_subscription(self, req: web.Request) -> web.Response:
        body = await req.json()
        sub_id = body.get("subscription_id", "").strip()
        if not sub_id:
            return _error("subscription_id is required", 400)
        ok, msg = self._az.ok("account", "set", "--subscription", sub_id)
        self._az.invalidate_cache("account", "show")
        return _ok(f"Subscription set to {sub_id}") if ok else _error(f"Failed: {msg}")

    async def list_resource_groups(self, _req: web.Request) -> web.Response:
        groups = self._az.json("group", "list") or []
        return web.json_response([
            {"name": g["name"], "location": g["location"]}
            for g in (groups if isinstance(groups, list) else [])
        ])

    # -- Copilot --

    async def copilot_status(self, _req: web.Request) -> web.Response:
        return web.json_response(self._gh.status())

    async def copilot_login(self, _req: web.Request) -> web.Response:
        status, info = self._gh.start_login()
        return web.json_response(
            {"status": status, **info}, status=500 if status == "error" else 200
        )

    async def copilot_set_token(self, req: web.Request) -> web.Response:
        body = await req.json()
        token = body.get("token", "").strip()
        if not token:
            return _error("Token is required", 400)
        cfg.write_env(GITHUB_TOKEN=token)
        return _ok("GitHub token saved")

    async def smoke_test(self, _req: web.Request) -> web.Response:
        runner = SmokeTestRunner(self._gh)
        result = await runner.run()
        return web.json_response(result, status=200 if result["status"] == "ok" else 500)

    # -- Tunnel --

    async def start_tunnel(self, req: web.Request) -> web.Response:
        body = await req.json()
        port = body.get("port", cfg.admin_port)
        result = self._tunnel.start(port)
        if not result:
            return _error(result.message)
        url = result.value

        endpoint_updated = False
        if cfg.env.read("BOT_NAME"):
            endpoint = url.rstrip("/") + "/api/messages"
            ok, _ = await run_sync(self._az.update_endpoint, endpoint)
            endpoint_updated = ok
            if ok:
                self._rebuild()

        return web.json_response({
            "status": "ok",
            "url": url,
            "message": result.message,
            "endpoint_updated": endpoint_updated,
        })

    async def stop_tunnel(self, _req: web.Request) -> web.Response:
        result = self._tunnel.stop()
        if not result:
            return _error(result.message)
        return web.json_response({"status": "ok", "message": result.message})

    async def toggle_tunnel_restriction(self, req: web.Request) -> web.Response:
        body = await req.json()
        restricted = bool(body.get("restricted", False))

        if restricted:
            if not self._store.bot_configured:
                return _error(
                    "Cannot enable: bot configuration incomplete.", 400
                )
            if not self._tunnel.is_active:
                return _error("Cannot enable: tunnel not active.", 400)

        cfg.write_env(TUNNEL_RESTRICTED="1" if restricted else "")
        state = "enabled" if restricted else "disabled"
        logger.info("Tunnel restriction %s", state)
        return web.json_response({
            "status": "ok", "restricted": restricted,
            "message": f"Tunnel restriction {state}",
        })

    # -- Bot config --

    async def get_bot_config(self, _req: web.Request) -> web.Response:
        from dataclasses import asdict
        return web.json_response(asdict(self._store.bot))

    async def save_bot_config(self, req: web.Request) -> web.Response:
        body = await req.json()
        self._store.save_bot(
            resource_group=body.get("resource_group", "polyclaw-rg"),
            location=body.get("location", "eastus"),
            display_name=body.get("display_name", "polyclaw"),
            bot_handle=body.get("bot_handle", ""),
        )
        return _ok("Bot configuration saved")

    # -- Channel config --

    async def get_channels_config(self, _req: web.Request) -> web.Response:
        safe = self._store.to_safe_dict()
        return web.json_response(safe.get("channels", {}))

    async def save_telegram_config(self, req: web.Request) -> web.Response:
        body = await req.json()
        token = body.get("token", "").strip()
        whitelist = body.get("whitelist", "").strip()
        if not token:
            return _error("Telegram bot token is required", 400)

        tok_ok, tok_detail = self._az.validate_telegram_token(token)
        if not tok_ok:
            return _error(f"Invalid Telegram token: {tok_detail}", 400)

        self._store.save_telegram(token=token, whitelist=whitelist)
        return web.json_response({
            "status": "ok", "message": f"Telegram config saved ({tok_detail})"
        })

    async def remove_telegram_config(self, _req: web.Request) -> web.Response:
        self._store.clear_telegram()
        return _ok("Telegram configuration removed")

    # -- Combined save --

    async def save_configuration(self, req: web.Request) -> web.Response:
        body = await req.json()
        steps: list[dict] = []

        tg = body.get("telegram", {})
        tg_token = tg.get("token", "").strip()
        tg_whitelist = tg.get("whitelist", "").strip()

        if tg_token:
            tok_ok, tok_detail = self._az.validate_telegram_token(tg_token)
            if not tok_ok:
                return _error(f"Invalid Telegram token: {tok_detail}", 400)
            steps.append({
                "step": "validate_token", "status": "ok", "detail": tok_detail
            })

        bot = body.get("bot", {})
        self._store.save_bot(
            resource_group=bot.get("resource_group", "polyclaw-rg"),
            location=bot.get("location", "eastus"),
            display_name=bot.get("display_name", "polyclaw"),
            bot_handle=bot.get("bot_handle", ""),
        )
        steps.append({
            "step": "bot_config", "status": "ok", "detail": "Saved"
        })

        kv_steps = await self._prerequisites_routes.ensure_keyvault_ready(
            location=bot.get("location", "eastus"),
        )
        steps.extend(kv_steps)

        kv_failed = any(s.get("status") == "failed" for s in kv_steps)
        if kv_failed:
            return web.json_response({
                "status": "error", "steps": steps,
                "message": "Key Vault creation failed",
            }, status=500)

        if tg_token:
            self._store.save_telegram(token=tg_token, whitelist=tg_whitelist)
            steps.append({
                "step": "telegram_config", "status": "ok",
                "detail": "Stored in Key Vault",
            })

        try:
            migrated = self._prerequisites_routes._migrate_existing_secrets()
            if migrated:
                steps.append({
                    "step": "migrate_env", "status": "ok",
                    "detail": f"Migrated {migrated} secret(s)",
                })
        except Exception as exc:
            logger.warning("Post-save migration failed: %s", exc)
            steps.append({
                "step": "migrate_env", "status": "warning",
                "detail": "Some secrets could not be migrated",
            })

        return web.json_response({
            "status": "ok", "steps": steps,
            "message": "Configuration saved securely",
        })

    # -- Infrastructure --

    async def infra_status(self, _req: web.Request) -> web.Response:
        result = await run_sync(self._provisioner.status)
        return web.json_response(result)

    async def infra_deploy(self, _req: web.Request) -> web.Response:
        decomm_steps = await run_sync(self._provisioner.decommission)
        prov_steps = await run_sync(self._provisioner.provision)
        self._rebuild()

        all_steps = decomm_steps + prov_steps
        prov_failed = any(s.get("status") == "failed" for s in prov_steps)
        return web.json_response({
            "status": "error" if prov_failed else "ok",
            "message": "Deploy completed with errors" if prov_failed else "Deployed",
            "steps": all_steps,
        }, status=500 if prov_failed else 200)

    async def infra_decommission(self, _req: web.Request) -> web.Response:
        steps = await run_sync(self._provisioner.decommission)
        self._rebuild()
        failed = any(s.get("status") == "failed" for s in steps)
        return web.json_response({
            "status": "error" if failed else "ok",
            "message": "Errors during decommission" if failed else "Decommissioned",
            "steps": steps,
        }, status=500 if failed else 200)

    # -- Runtime config --

    async def get_config(self, _req: web.Request) -> web.Response:
        raw = {
            "COPILOT_MODEL": cfg.env.read("COPILOT_MODEL") or cfg.copilot_model,
            "BOT_PORT": cfg.env.read("BOT_PORT") or str(cfg.bot_port),
            "GITHUB_TOKEN": cfg.env.read("GITHUB_TOKEN"),
        }
        for key in raw:
            if key in SECRET_ENV_KEYS and raw[key]:
                raw[key] = "****"
        return web.json_response(raw)

    async def save_config(self, req: web.Request) -> web.Response:
        cfg.write_env(**(await req.json()))
        return _ok("Config saved")

    # -- Lock Down Mode --

    async def lockdown_status(self, _req: web.Request) -> web.Response:
        return web.json_response({
            "lockdown_mode": cfg.lockdown_mode,
            "tunnel_restricted": cfg.tunnel_restricted,
        })

    async def lockdown_toggle(self, req: web.Request) -> web.Response:
        body = await req.json()
        enabled = bool(body.get("enabled", False))

        if enabled:
            if cfg.lockdown_mode:
                return _ok("Already enabled")
            cfg.write_env(LOCKDOWN_MODE="1", TUNNEL_RESTRICTED="1")
            try:
                self._az.ok("logout")
                self._az.invalidate_cache("account", "show")
            except Exception:
                pass
            return web.json_response({
                "status": "ok", "lockdown_mode": True,
                "message": "Lock Down Mode enabled.",
            })
        else:
            if not cfg.lockdown_mode:
                return _ok("Already disabled")
            cfg.write_env(LOCKDOWN_MODE="", TUNNEL_RESTRICTED="")
            return web.json_response({
                "status": "ok", "lockdown_mode": False,
                "message": "Lock Down Mode disabled.",
            })


def _ok(message: str) -> web.Response:
    return web.json_response({"status": "ok", "message": message})


def _error(message: str, status: int = 500) -> web.Response:
    return web.json_response({"status": "error", "message": message}, status=status)
