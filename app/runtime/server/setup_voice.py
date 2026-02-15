"""Voice setup routes -- ``/api/setup/voice/*``."""

from __future__ import annotations

import functools
import logging
import secrets

from aiohttp import web

from ..config.settings import cfg
from ..services.azure import AzureCLI
from ..state.infra_config import InfraConfigStore
from ..util.async_helpers import run_sync

logger = logging.getLogger(__name__)


class VoiceSetupRoutes:
    """ACS + Azure OpenAI provisioning, phone config, and decommissioning."""

    def __init__(self, az: AzureCLI, store: InfraConfigStore) -> None:
        self._az = az
        self._store = store

    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get("/api/setup/voice/config", self.get_config)
        router.add_post("/api/setup/voice/deploy", self.deploy)
        router.add_post("/api/setup/voice/connect", self.connect_existing)
        router.add_post("/api/setup/voice/phone", self.save_phone)
        router.add_post("/api/setup/voice/decommission", self.decommission)
        router.add_get("/api/setup/voice/aoai/list", self.list_aoai)
        router.add_get("/api/setup/voice/aoai/deployments", self.list_aoai_deployments)
        router.add_post("/api/setup/voice/aoai/validate", self.validate_aoai)
        router.add_get("/api/setup/voice/acs/list", self.list_acs)
        router.add_get("/api/setup/voice/acs/phones", self.list_acs_phones)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    async def get_config(self, _req: web.Request) -> web.Response:
        vc = self._store.to_safe_dict().get("channels", {}).get("voice_call", {})
        if vc.get("acs_resource_name"):
            rg = vc.get("voice_resource_group") or vc.get("resource_group")
            if rg:
                account = self._az.account_info()
                sub_id = account.get("id", "") if account else ""
                if sub_id:
                    vc["portal_phone_url"] = (
                        f"https://portal.azure.com/#@/resource/subscriptions/{sub_id}"
                        f"/resourceGroups/{rg}"
                        f"/providers/Microsoft.Communication"
                        f"/CommunicationServices/{vc['acs_resource_name']}"
                        f"/phonenumbers"
                    )
        return web.json_response(vc)

    # ------------------------------------------------------------------
    # Deploy
    # ------------------------------------------------------------------

    async def deploy(self, req: web.Request) -> web.Response:
        body = await req.json()
        location = body.get("location", "swedencentral").strip()
        voice_rg = body.get("voice_resource_group", "").strip() or "octoclaw-voice-rg"
        logger.info("Voice deploy started: voice_rg=%s, location=%s", voice_rg, location)

        steps: list[dict] = []

        if not await self._ensure_rg(voice_rg, location, steps):
            return _voice_fail(steps)

        acs_name, conn_str = await self._create_acs(voice_rg, steps)
        if not conn_str:
            return _voice_fail(steps)

        aoai_name, aoai_endpoint, aoai_key, deployment_name = await self._create_aoai(
            voice_rg, location, steps
        )
        if not aoai_endpoint:
            return _voice_fail(steps)

        if not aoai_key:
            await self._ensure_rbac(aoai_name, voice_rg, steps)

        self._persist_config(
            voice_rg, location, acs_name, conn_str,
            aoai_name, aoai_endpoint, aoai_key, deployment_name, steps,
        )
        logger.info("Voice deploy completed: acs=%s, aoai=%s", acs_name, aoai_name)

        reinit = req.app.get("_reinit_voice")
        if reinit:
            reinit()

        return web.json_response({
            "status": "ok",
            "steps": steps,
            "message": (
                "Voice infrastructure deployed."
                " Now purchase a phone number in the Azure Portal."
            ),
        })

    # ------------------------------------------------------------------
    # Phone
    # ------------------------------------------------------------------

    async def save_phone(self, req: web.Request) -> web.Response:
        body = await req.json()
        phone = body.get("phone_number", "").strip()
        target = body.get("target_number", "").strip()

        updates: dict[str, str] = {}
        env_updates: dict[str, str] = {}

        if phone:
            if not phone.startswith("+"):
                return _error("Source phone number must be in E.164 format (e.g. +14155551234)", 400)
            updates["acs_source_number"] = phone
            env_updates["ACS_SOURCE_NUMBER"] = phone

        if target:
            if not target.startswith("+"):
                return _error("Target phone number must be in E.164 format (e.g. +41781234567)", 400)
            updates["voice_target_number"] = target
            env_updates["VOICE_TARGET_NUMBER"] = target

        if not updates:
            return _error("At least one phone number is required", 400)

        self._store.save_voice_call(**updates)
        cfg.write_env(**env_updates)

        reinit = req.app.get("_reinit_voice")
        if reinit:
            reinit()

        return _ok("Phone number(s) saved")

    # ------------------------------------------------------------------
    # Decommission
    # ------------------------------------------------------------------

    async def decommission(self, req: web.Request) -> web.Response:
        vc = self._store.channels.voice_call
        voice_rg = vc.voice_resource_group or vc.resource_group
        steps: list[dict] = []

        if voice_rg:
            rg_exists = await run_sync(self._az.json, "group", "show", "--name", voice_rg)
            if rg_exists:
                ok, msg = await run_sync(
                    self._az.ok, "group", "delete", "--name", voice_rg, "--yes", "--no-wait",
                )
                steps.append({
                    "step": "voice_rg_delete",
                    "status": "ok" if ok else "failed",
                    "name": voice_rg,
                    "detail": f"Deleting {voice_rg}" if ok else msg,
                })
            else:
                steps.append({"step": "voice_rg_delete", "status": "skip", "detail": "RG not found"})
        else:
            rg = vc.resource_group
            if vc.acs_resource_name and rg:
                ok, _ = await run_sync(
                    self._az.ok, "communication", "delete",
                    "--name", vc.acs_resource_name, "--resource-group", rg, "--yes",
                )
                steps.append({
                    "step": "acs_resource",
                    "status": "ok" if ok else "failed",
                    "name": vc.acs_resource_name,
                })

            if vc.azure_openai_resource_name and rg:
                ok, _ = await run_sync(
                    self._az.ok, "cognitiveservices", "account", "delete",
                    "--name", vc.azure_openai_resource_name, "--resource-group", rg, "--yes",
                )
                steps.append({
                    "step": "aoai_resource",
                    "status": "ok" if ok else "failed",
                    "name": vc.azure_openai_resource_name,
                })

        self._store.clear_voice_call()
        cfg.write_env(
            ACS_CONNECTION_STRING="",
            ACS_SOURCE_NUMBER="",
            VOICE_TARGET_NUMBER="",
            AZURE_OPENAI_ENDPOINT="",
            AZURE_OPENAI_API_KEY="",
            AZURE_OPENAI_REALTIME_DEPLOYMENT="",
            ACS_CALLBACK_TOKEN="",
        )

        return web.json_response({
            "status": "ok",
            "steps": steps,
            "message": "Voice infrastructure decommissioned",
        })

    # ------------------------------------------------------------------
    # Discovery: AOAI
    # ------------------------------------------------------------------

    async def list_aoai(self, _req: web.Request) -> web.Response:
        resources = await run_sync(
            self._az.json, "resource", "list",
            "--resource-type", "Microsoft.CognitiveServices/accounts",
        )
        if not isinstance(resources, list):
            return web.json_response([])

        return web.json_response([
            {
                "name": r.get("name", ""),
                "resource_group": r.get("resourceGroup", ""),
                "location": r.get("location", ""),
            }
            for r in resources
            if r.get("kind") == "OpenAI"
        ])

    async def list_aoai_deployments(self, req: web.Request) -> web.Response:
        name = req.query.get("name", "").strip()
        rg = req.query.get("resource_group", "").strip()
        if not name or not rg:
            return _error("name and resource_group are required", 400)

        deployments = await run_sync(
            self._az.json, "cognitiveservices", "account", "deployment", "list",
            "--name", name, "--resource-group", rg,
        )
        if not isinstance(deployments, list):
            return web.json_response([])

        return web.json_response([
            {
                "deployment_name": d.get("name", ""),
                "model_name": d.get("properties", {}).get("model", {}).get("name", ""),
                "model_version": d.get("properties", {}).get("model", {}).get("version", ""),
                "model_format": d.get("properties", {}).get("model", {}).get("format", ""),
            }
            for d in deployments
        ])

    async def validate_aoai(self, req: web.Request) -> web.Response:
        body = await req.json()
        name = body.get("name", "").strip()
        rg = body.get("resource_group", "").strip()
        if not name or not rg:
            return _error("name and resource_group are required", 400)

        deployments = await run_sync(
            self._az.json, "cognitiveservices", "account", "deployment", "list",
            "--name", name, "--resource-group", rg,
        )
        if not isinstance(deployments, list):
            return web.json_response({
                "valid": False,
                "message": f"Cannot list deployments for {name}",
                "deployments": [],
            })

        realtime_models = {
            "gpt-4o-realtime-preview",
            "gpt-realtime-mini",
            "gpt-4o-mini-realtime-preview",
        }
        found = []
        for d in deployments:
            model = d.get("properties", {}).get("model", {})
            model_name = model.get("name", "")
            found.append({
                "deployment_name": d.get("name", ""),
                "model_name": model_name,
                "model_version": model.get("version", ""),
                "is_realtime": model_name in realtime_models,
            })

        has_realtime = any(f["is_realtime"] for f in found)
        return web.json_response({
            "valid": has_realtime,
            "message": (
                "Realtime model deployment found"
                if has_realtime
                else "No realtime model deployment found. Deploy gpt-realtime-mini or gpt-4o-realtime-preview."
            ),
            "deployments": found,
        })

    # ------------------------------------------------------------------
    # Discovery: ACS
    # ------------------------------------------------------------------

    async def list_acs(self, _req: web.Request) -> web.Response:
        resources = await run_sync(self._az.json, "communication", "list")
        if not isinstance(resources, list):
            return web.json_response([])

        return web.json_response([
            {
                "name": r.get("name", ""),
                "resource_group": r.get("resourceGroup", ""),
                "location": r.get("location", ""),
            }
            for r in resources
        ])

    async def list_acs_phones(self, req: web.Request) -> web.Response:
        name = req.query.get("name", "").strip()
        rg = req.query.get("resource_group", "").strip()
        if not name or not rg:
            return _error("name and resource_group are required", 400)

        keys = await run_sync(
            self._az.json, "communication", "list-key",
            "--name", name, "--resource-group", rg,
        )
        conn_str = keys.get("primaryConnectionString", "") if isinstance(keys, dict) else ""
        if not conn_str:
            return web.json_response([])

        phones = await run_sync(
            self._az.json, "communication", "phonenumber", "list",
            "--connection-string", conn_str,
        )
        if not isinstance(phones, list):
            return web.json_response([])

        return web.json_response([
            {"phone_number": p.get("phoneNumber", "")}
            for p in phones
            if p.get("phoneNumber")
        ])

    # ------------------------------------------------------------------
    # Connect existing
    # ------------------------------------------------------------------

    async def connect_existing(self, req: web.Request) -> web.Response:
        body = await req.json()
        steps: list[dict] = []

        aoai_name = body.get("aoai_name", "").strip()
        aoai_rg = body.get("aoai_resource_group", "").strip()
        aoai_deployment = body.get("aoai_deployment", "").strip() or "gpt-realtime-mini"

        if not aoai_name or not aoai_rg:
            return _error("aoai_name and aoai_resource_group are required", 400)

        aoai_info = await run_sync(
            self._az.json, "cognitiveservices", "account", "show",
            "--name", aoai_name, "--resource-group", aoai_rg,
        )
        if not isinstance(aoai_info, dict):
            return _error(f"Azure OpenAI resource '{aoai_name}' not found in RG '{aoai_rg}'", 404)

        aoai_endpoint = aoai_info.get("properties", {}).get("endpoint", "")
        steps.append({"step": "aoai_resource", "status": "ok", "name": f"{aoai_name} (existing)"})

        deployments = await run_sync(
            self._az.json, "cognitiveservices", "account", "deployment", "list",
            "--name", aoai_name, "--resource-group", aoai_rg,
        )
        dep_found = isinstance(deployments, list) and any(
            d.get("name") == aoai_deployment for d in deployments
        )
        if not dep_found:
            steps.append({
                "step": "aoai_deployment", "status": "failed",
                "name": aoai_deployment,
                "detail": f"Deployment '{aoai_deployment}' not found on {aoai_name}",
            })
            return _voice_fail(steps)

        steps.append({"step": "aoai_deployment", "status": "ok", "name": f"{aoai_deployment} (verified)"})

        aoai_keys = await run_sync(
            self._az.json, "cognitiveservices", "account", "keys", "list",
            "--name", aoai_name, "--resource-group", aoai_rg,
        )
        aoai_key = aoai_keys.get("key1", "") if isinstance(aoai_keys, dict) else ""
        if aoai_key:
            steps.append({"step": "aoai_keys", "status": "ok"})
        else:
            logger.info("AOAI key retrieval skipped (disableLocalAuth likely true)")
            steps.append({
                "step": "aoai_keys", "status": "ok",
                "detail": "Key-based auth disabled; will use Entra ID (DefaultAzureCredential)",
            })

        acs_name = body.get("acs_name", "").strip()
        acs_rg = body.get("acs_resource_group", "").strip()
        conn_str = ""
        voice_rg = aoai_rg

        if acs_name and acs_rg:
            keys = await run_sync(
                self._az.json, "communication", "list-key",
                "--name", acs_name, "--resource-group", acs_rg,
            )
            conn_str = keys.get("primaryConnectionString", "") if isinstance(keys, dict) else ""
            if not conn_str:
                steps.append({
                    "step": "acs_resource", "status": "failed",
                    "name": acs_name, "detail": "Cannot retrieve connection string",
                })
                return _voice_fail(steps)
            steps.append({"step": "acs_resource", "status": "ok", "name": f"{acs_name} (existing)"})
            voice_rg = acs_rg
        else:
            voice_rg = aoai_rg
            if not await self._ensure_rg(voice_rg, "Global", steps):
                return _voice_fail(steps)
            acs_name, conn_str = await self._create_acs(voice_rg, steps)
            if not conn_str:
                return _voice_fail(steps)

        location = aoai_info.get("location", "swedencentral")

        if not aoai_key:
            await self._ensure_rbac(aoai_name, aoai_rg, steps)

        self._persist_config(
            voice_rg, location, acs_name, conn_str,
            aoai_name, aoai_endpoint, aoai_key, aoai_deployment, steps,
        )

        phone = body.get("phone_number", "").strip()
        if phone:
            self._store.save_voice_call(acs_source_number=phone)
            cfg.write_env(ACS_SOURCE_NUMBER=phone)
            steps.append({"step": "phone_number", "status": "ok", "name": phone})

        target = body.get("target_number", "").strip()
        if target:
            self._store.save_voice_call(voice_target_number=target)
            cfg.write_env(VOICE_TARGET_NUMBER=target)
            steps.append({"step": "target_number", "status": "ok", "name": target})

        logger.info("Voice connect completed: acs=%s, aoai=%s", acs_name, aoai_name)

        reinit = req.app.get("_reinit_voice")
        if reinit:
            reinit()

        return web.json_response({
            "status": "ok",
            "steps": steps,
            "message": "Connected to existing Azure resources.",
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_rbac(
        self, aoai_name: str, rg: str, steps: list[dict],
    ) -> None:
        account = self._az.account_info()
        if not account:
            steps.append({
                "step": "rbac_assign", "status": "skip",
                "detail": "Cannot determine current principal (az account show failed)",
            })
            return

        principal_id = ""
        principal_type = "User"

        user_info = await run_sync(
            functools.partial(self._az.json, "ad", "signed-in-user", "show", quiet=True),
        )
        if isinstance(user_info, dict) and user_info.get("id"):
            principal_id = user_info["id"]
        else:
            sp_id = account.get("user", {}).get("name", "")
            if sp_id:
                sp_info = await run_sync(
                    functools.partial(self._az.json, "ad", "sp", "show", "--id", sp_id, quiet=True),
                )
                if isinstance(sp_info, dict) and sp_info.get("id"):
                    principal_id = sp_info["id"]
                    principal_type = "ServicePrincipal"

        if not principal_id:
            steps.append({
                "step": "rbac_assign", "status": "skip",
                "detail": "Cannot determine principal ID for RBAC assignment",
            })
            return

        aoai_info = await run_sync(
            self._az.json, "cognitiveservices", "account", "show",
            "--name", aoai_name, "--resource-group", rg,
        )
        scope = aoai_info.get("id", "") if isinstance(aoai_info, dict) else ""
        if not scope:
            steps.append({
                "step": "rbac_assign", "status": "skip",
                "detail": f"Cannot resolve resource ID for {aoai_name}",
            })
            return

        role = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"
        logger.info("Assigning Cognitive Services OpenAI User role: principal=%s", principal_id)
        ok, msg = await run_sync(
            self._az.ok, "role", "assignment", "create",
            "--assignee-object-id", principal_id,
            "--assignee-principal-type", principal_type,
            "--role", role, "--scope", scope,
        )
        if ok:
            steps.append({"step": "rbac_assign", "status": "ok", "detail": "Cognitive Services OpenAI User"})
        elif "already exists" in (msg or "").lower() or "conflict" in (msg or "").lower():
            steps.append({"step": "rbac_assign", "status": "ok", "detail": "Already assigned"})
        else:
            steps.append({
                "step": "rbac_assign", "status": "warning",
                "detail": f"Role assignment failed (non-fatal): {msg}",
            })
            logger.warning("RBAC role assignment failed (non-fatal): %s", msg)

    async def _ensure_rg(self, rg: str, location: str, steps: list[dict]) -> bool:
        existing = await run_sync(self._az.json, "group", "show", "--name", rg)
        if existing:
            steps.append({"step": "resource_group", "status": "ok", "name": f"{rg} (existing)"})
            return True

        result = await run_sync(
            self._az.json, "group", "create", "--name", rg, "--location", location,
        )
        steps.append({"step": "resource_group", "status": "ok" if result else "failed", "name": rg})
        if not result:
            logger.error("Voice deploy FAILED at resource group creation: %s", self._az.last_stderr)
        return bool(result)

    async def _create_acs(self, rg: str, steps: list[dict]) -> tuple[str, str]:
        acs_name = f"octoclaw-acs-{secrets.token_hex(4)}"
        acs = await run_sync(
            self._az.json, "communication", "create",
            "--name", acs_name, "--location", "Global",
            "--data-location", "United States", "--resource-group", rg,
        )
        steps.append({"step": "acs_resource", "status": "ok" if acs else "failed", "name": acs_name})
        if not acs:
            logger.error("Voice deploy FAILED at ACS creation: %s", self._az.last_stderr)
            return "", ""

        keys = await run_sync(
            self._az.json, "communication", "list-key",
            "--name", acs_name, "--resource-group", rg,
        )
        conn_str = keys.get("primaryConnectionString", "") if isinstance(keys, dict) else ""
        steps.append({"step": "acs_keys", "status": "ok" if conn_str else "failed"})
        if not conn_str:
            logger.error("Voice deploy FAILED retrieving ACS keys: %s", self._az.last_stderr)
            return acs_name, ""
        return acs_name, conn_str

    async def _create_aoai(
        self, rg: str, location: str, steps: list[dict],
    ) -> tuple[str, str, str, str]:
        aoai_name = f"octoclaw-aoai-{secrets.token_hex(4)}"
        deployment_name = "gpt-realtime-mini"

        aoai = await run_sync(
            self._az.json, "cognitiveservices", "account", "create",
            "--name", aoai_name, "--resource-group", rg,
            "--location", location, "--kind", "OpenAI",
            "--sku", "S0", "--custom-domain", aoai_name,
        )
        steps.append({"step": "aoai_resource", "status": "ok" if aoai else "failed", "name": aoai_name})
        if not aoai:
            logger.error("Voice deploy FAILED at AOAI creation: %s", self._az.last_stderr)
            return "", "", "", ""

        dep = await run_sync(
            self._az.json, "cognitiveservices", "account", "deployment", "create",
            "--name", aoai_name, "--resource-group", rg,
            "--deployment-name", deployment_name,
            "--model-name", "gpt-realtime-mini",
            "--model-version", "2025-10-06",
            "--model-format", "OpenAI",
            "--sku-capacity", "1", "--sku-name", "GlobalStandard",
        )
        steps.append({"step": "aoai_deployment", "status": "ok" if dep else "failed", "name": deployment_name})
        if not dep:
            logger.error("Voice deploy FAILED at model deployment: %s", self._az.last_stderr)
            return aoai_name, "", "", ""

        aoai_info = await run_sync(
            self._az.json, "cognitiveservices", "account", "show",
            "--name", aoai_name, "--resource-group", rg,
        )
        aoai_endpoint = ""
        if isinstance(aoai_info, dict):
            aoai_endpoint = aoai_info.get("properties", {}).get("endpoint", "")

        aoai_keys = await run_sync(
            self._az.json, "cognitiveservices", "account", "keys", "list",
            "--name", aoai_name, "--resource-group", rg,
        )
        aoai_key = aoai_keys.get("key1", "") if isinstance(aoai_keys, dict) else ""

        if not aoai_endpoint:
            steps.append({"step": "aoai_keys", "status": "failed"})
            logger.error("Voice deploy FAILED retrieving AOAI endpoint")
            return aoai_name, "", "", ""

        if aoai_key:
            steps.append({"step": "aoai_keys", "status": "ok"})
        else:
            steps.append({"step": "aoai_keys", "status": "ok", "detail": "Using Entra ID auth"})

        return aoai_name, aoai_endpoint, aoai_key, deployment_name

    def _persist_config(
        self,
        voice_rg: str,
        location: str,
        acs_name: str,
        conn_str: str,
        aoai_name: str,
        aoai_endpoint: str,
        aoai_key: str,
        deployment_name: str,
        steps: list[dict],
    ) -> None:
        self._store.save_voice_call(
            acs_resource_name=acs_name,
            acs_connection_string=conn_str,
            azure_openai_resource_name=aoai_name,
            azure_openai_endpoint=aoai_endpoint,
            azure_openai_api_key=aoai_key,
            azure_openai_realtime_deployment=deployment_name,
            resource_group=voice_rg,
            voice_resource_group=voice_rg,
            location=location,
        )
        callback_token = cfg.acs_callback_token
        cfg.write_env(
            ACS_CONNECTION_STRING=conn_str,
            ACS_SOURCE_NUMBER="",
            AZURE_OPENAI_ENDPOINT=aoai_endpoint,
            AZURE_OPENAI_API_KEY=aoai_key,
            AZURE_OPENAI_REALTIME_DEPLOYMENT=deployment_name,
            ACS_CALLBACK_TOKEN=callback_token,
        )
        steps.append({"step": "persist_config", "status": "ok"})


def _ok(message: str) -> web.Response:
    return web.json_response({"status": "ok", "message": message})


def _error(message: str, status: int = 500) -> web.Response:
    return web.json_response({"status": "error", "message": message}, status=status)


def _voice_fail(steps: list[dict]) -> web.Response:
    failed = [s for s in steps if s.get("status") == "failed"]
    msg = failed[0].get("name", "Unknown step") if failed else "Unknown error"
    return web.json_response(
        {"status": "error", "steps": steps, "message": f"Voice deploy failed at: {msg}"},
    )
