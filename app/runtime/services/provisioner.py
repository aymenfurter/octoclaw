"""Infrastructure provisioner -- reconcile Azure state with config."""

from __future__ import annotations

import logging
from typing import Any

from ..config.settings import cfg
from ..state.deploy_state import DeploymentRecord, DeployStateStore
from ..state.infra_config import InfraConfigStore
from .azure import AzureCLI
from .deployer import BotDeployer, DeployRequest
from .tunnel import CloudflareTunnel

logger = logging.getLogger(__name__)


class Provisioner:
    """Orchestrates full infrastructure lifecycle from config."""

    def __init__(
        self,
        az: AzureCLI,
        deployer: BotDeployer,
        tunnel: CloudflareTunnel,
        store: InfraConfigStore,
        deploy_store: DeployStateStore | None = None,
    ) -> None:
        self._az = az
        self._deployer = deployer
        self._tunnel = tunnel
        self._store = store
        self._deploy_store = deploy_store

    def provision(self) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        bc = self._store.bot
        logger.info("Provisioning started")

        if not self._store.bot_configured:
            logger.info("No bot configured -- skipping provisioning")
            steps.append({"step": "bot_config", "status": "skip", "detail": "No bot configured"})
            return steps

        if self._deploy_store:
            rec = self._deploy_store.current_local()
            if not rec:
                rec = DeploymentRecord.new(kind="local")
                self._deploy_store.register(rec)
                logger.info("Created new local deployment record: %s", rec.deploy_id)

        logger.info("Provision step 1/3: Ensuring tunnel...")
        tunnel_url = self._ensure_tunnel(steps)
        if not tunnel_url:
            logger.error("Provisioning aborted: tunnel failed")
            return steps

        logger.info("Provision step 2/3: Ensuring bot resource...")
        if not self._ensure_bot(bc, tunnel_url, steps):
            logger.error("Provisioning aborted: bot deployment failed")
            return steps

        logger.info("Provision step 3/3: Ensuring channels...")
        self._ensure_channels(steps)
        logger.info("Provisioning completed: %d steps", len(steps))
        return steps

    def _ensure_tunnel(self, steps: list[dict]) -> str | None:
        if self._tunnel.is_active and self._tunnel.url:
            logger.info("Tunnel already active: %s", self._tunnel.url)
            steps.append({"step": "tunnel", "status": "ok", "detail": self._tunnel.url})
            return self._tunnel.url

        logger.info("Starting tunnel on port %s...", cfg.admin_port)
        result = self._tunnel.start(cfg.admin_port)
        if result:
            url = result.value
            logger.info("Tunnel started: %s", url)
            steps.append({"step": "tunnel", "status": "ok", "detail": url})
            return url

        logger.error("Tunnel failed to start: %s", result.message)
        steps.append({"step": "tunnel", "status": "failed", "detail": result.message})
        return None

    def _ensure_bot(self, bc: Any, tunnel_url: str, steps: list[dict]) -> bool:
        existing_name = cfg.env.read("BOT_NAME")
        endpoint = tunnel_url.rstrip("/") + "/api/messages"

        if existing_name:
            # Always delete the existing bot so we start with a clean slate.
            logger.info(
                "Bot '%s' already deployed -- deleting before fresh deploy",
                existing_name,
            )
            cleanup_result = self._deployer.delete()
            steps.extend(cleanup_result.steps)
            steps.append({
                "step": "bot_cleanup",
                "status": "ok" if cleanup_result.ok else "failed",
                "detail": f"Deleted {existing_name}" if cleanup_result.ok else cleanup_result.error,
            })

        logger.info(
            "Starting fresh bot deployment (rg=%s, location=%s)",
            bc.resource_group, bc.location,
        )
        req = DeployRequest(
            resource_group=bc.resource_group, location=bc.location,
            display_name=bc.display_name, bot_handle=bc.bot_handle,
            endpoint_url=tunnel_url,
        )
        result = self._deployer.deploy(req)
        steps.extend(result.steps)
        if result.ok:
            steps.append({"step": "bot_deploy", "status": "ok", "detail": result.bot_handle})
            ok, msg = self._az.update_endpoint(endpoint)
            steps.append({"step": "bot_endpoint", "status": "ok" if ok else "failed", "detail": msg})
        else:
            steps.append({"step": "bot_deploy", "status": "failed", "detail": result.error})
        return result.ok

    def _ensure_channels(self, steps: list[dict]) -> None:
        tg = self._store.channels.telegram
        if tg.token:
            tok_ok, tok_detail = self._az.validate_telegram_token(tg.token)
            if not tok_ok:
                steps.append({"step": "telegram_validate", "status": "failed", "detail": tok_detail})
                return
            steps.append({"step": "telegram_validate", "status": "ok", "detail": tok_detail})
            # Pass validated_name so configure_telegram skips a redundant API call.
            ok, msg = self._az.configure_telegram(tg.token, validated_name=tok_detail)
            steps.append({"step": "telegram_channel", "status": "ok" if ok else "failed", "detail": msg})
            if ok and tg.whitelist:
                cfg.write_env(TELEGRAM_WHITELIST=tg.whitelist)
        else:
            steps.append({"step": "telegram", "status": "skip", "detail": "Not configured"})

    def decommission(self) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        logger.info("Decommissioning started")

        rg = cfg.env.read("BOT_RESOURCE_GROUP")
        name = cfg.env.read("BOT_NAME")
        app_id = cfg.env.read("BOT_APP_ID")
        logger.info(
            "Current state: rg=%s, bot=%s, app_id=%s",
            rg, name, app_id[:12] + "..." if app_id else None,
        )

        if name and rg:
            bot_exists = self._az.json("bot", "show", "--resource-group", rg, "--name", name) is not None
            if bot_exists and self._store.telegram_configured:
                ok, msg = self._az.remove_channel("telegram")
                steps.append({"step": "telegram_remove", "status": "ok" if ok else "failed", "detail": msg})
            elif not bot_exists:
                steps.append({"step": "telegram_remove", "status": "skip", "detail": "Bot resource not found"})

        if name:
            result = self._deployer.delete()
            steps.extend(result.steps)
            steps.append({
                "step": "bot_delete",
                "status": "ok" if result.ok else "failed",
                "detail": "Bot deleted" if result.ok else (result.error or "Failed"),
            })
        else:
            steps.append({"step": "bot_delete", "status": "skip", "detail": "No bot deployed"})

        voice_rg = self._store.channels.voice_call.voice_resource_group or ""
        prereq_rg = cfg.env.read("KEY_VAULT_RG") or ""
        protected_rgs = {rg_name for rg_name in (voice_rg, prereq_rg) if rg_name}

        if rg:
            if rg in protected_rgs:
                reason = []
                if rg == voice_rg:
                    reason.append("voice")
                if rg == prereq_rg:
                    reason.append("prerequisites")
                label = " & ".join(reason)
                logger.info("Skipping RG deletion: %s is the %s resource group", rg, label)
                steps.append({"step": "resource_group_delete", "status": "skip", "detail": f"{rg} is the {label} RG -- not deleting"})
            else:
                rg_exists = self._az.json("group", "show", "--name", rg) is not None
                if rg_exists:
                    ok, msg = self._az.ok("group", "delete", "--name", rg, "--yes", "--no-wait")
                    steps.append({"step": "resource_group_delete", "status": "ok" if ok else "failed", "detail": f"Deleting {rg}" if ok else msg})
                else:
                    steps.append({"step": "resource_group_delete", "status": "skip", "detail": "RG not found"})

        cfg.write_env(
            BOT_APP_ID="", BOT_APP_PASSWORD="", BOT_APP_TENANT_ID="",
            BOT_RESOURCE_GROUP="", BOT_NAME="",
        )

        if self._deploy_store:
            rec = self._deploy_store.current_local()
            if rec:
                rec.mark_stopped()
                self._deploy_store.update(rec)

        return steps

    def status(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "config": self._store.to_safe_dict(),
            "provisioned": {},
            "in_sync": True,
        }

        prov: dict[str, Any] = {}
        prov["tunnel"] = {"active": self._tunnel.is_active, "url": self._tunnel.url}
        if not self._tunnel.is_active:
            result["in_sync"] = False

        bot_name = cfg.env.read("BOT_NAME")
        bot_rg = cfg.env.read("BOT_RESOURCE_GROUP")
        bot_deployed = bool(bot_name)
        prov["bot"] = {
            "deployed": bot_deployed, "name": bot_name or None,
            "resource_group": bot_rg or None,
            "app_id": (cfg.bot_app_id[:12] + "...") if cfg.bot_app_id else None,
        }
        if self._store.bot_configured and not bot_deployed:
            result["in_sync"] = False

        channels: dict[str, Any] = {}
        if self._store.telegram_configured:
            if bot_deployed:
                live_channels = self._az.get_channels()
                tg_live = live_channels.get("telegram", False)
                channels["telegram"] = {"live": tg_live}
                if not tg_live:
                    result["in_sync"] = False
            else:
                channels["telegram"] = {"live": False}
                result["in_sync"] = False
        prov["channels"] = channels

        result["provisioned"] = prov
        return result
