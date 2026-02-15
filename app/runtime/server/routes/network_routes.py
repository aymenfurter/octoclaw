"""Network info API routes -- /api/network/*."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from aiohttp import ClientSession, ClientTimeout, web

from ...config.settings import cfg
from ...services.azure import AzureCLI
from ...services.tunnel import CloudflareTunnel
from ...state.foundry_iq_config import FoundryIQConfigStore
from ...state.sandbox_config import SandboxConfigStore

logger = logging.getLogger(__name__)

# Prefixes that the tunnel restriction middleware allows through
_TUNNEL_ALLOWED_PREFIXES = (
    "/health",
    "/api/messages",
    "/acs",
    "/realtime-acs",
    "/api/voice/acs-callback",
    "/api/voice/media-streaming",
)


def _detect_deploy_mode() -> str:
    """Return 'docker', 'aca', or 'local' based on runtime environment."""
    if os.getenv("WEBSITE_SITE_NAME") or os.getenv("CONTAINER_APP_NAME"):
        return "aca"
    if os.getenv("OCTOCLAW_CONTAINER") == "1":
        return "docker"
    return "local"


def _classify_endpoint(method: str, path: str) -> str:
    """Classify an endpoint into a category for display grouping."""
    if path.startswith("/api/messages") or path.startswith("/acs") or path.startswith("/realtime-acs"):
        return "bot"
    if path.startswith("/api/voice/") or path.startswith("/api/setup/voice/"):
        return "voice"
    if path.startswith("/api/chat/") or path.startswith("/api/models"):
        return "chat"
    if path.startswith("/api/setup/"):
        return "setup"
    if path.startswith("/api/foundry-iq/"):
        return "foundry-iq"
    if path.startswith("/api/sandbox/"):
        return "sandbox"
    if path.startswith("/api/network/"):
        return "network"
    if path.startswith("/api/"):
        return "admin"
    if path == "/health":
        return "health"
    return "frontend"


def _is_tunnel_exposed(path: str) -> bool:
    """Return True if the path would be allowed through in restricted tunnel mode."""
    return any(path.startswith(pfx) for pfx in _TUNNEL_ALLOWED_PREFIXES)


class NetworkRoutes:
    """Provides runtime network info: endpoints, components, tunnel mode."""

    def __init__(
        self,
        tunnel: CloudflareTunnel,
        az: AzureCLI | None = None,
        sandbox_store: SandboxConfigStore | None = None,
        foundry_iq_store: FoundryIQConfigStore | None = None,
    ) -> None:
        self._tunnel = tunnel
        self._az = az
        self._sandbox_store = sandbox_store
        self._foundry_iq_store = foundry_iq_store

    def register(self, router: web.UrlDispatcher) -> None:
        router.add_get("/api/network/info", self._info)
        router.add_get("/api/network/endpoints", self._endpoints)
        router.add_get("/api/network/probe", self._probe)
        router.add_get("/api/network/resource-audit", self._resource_audit)

    async def _info(self, req: web.Request) -> web.Response:
        """Return full network topology info."""
        cfg.reload()
        deploy_mode = _detect_deploy_mode()
        admin_port = cfg.admin_port

        # Collect registered endpoints from the live app router
        endpoints = self._collect_endpoints(req.app)

        # Build component info (what network connections are configured)
        components = self._build_components(deploy_mode)

        tunnel_info: dict[str, Any] = {
            "active": self._tunnel.is_active,
            "url": self._tunnel.url,
            "restricted": cfg.tunnel_restricted,
        }

        return web.json_response({
            "deploy_mode": deploy_mode,
            "admin_port": admin_port,
            "tunnel": tunnel_info,
            "lockdown_mode": cfg.lockdown_mode,
            "components": components,
            "endpoints": endpoints,
        })

    async def _endpoints(self, req: web.Request) -> web.Response:
        """Return just the list of registered endpoints."""
        endpoints = self._collect_endpoints(req.app)
        return web.json_response(endpoints)

    # ------------------------------------------------------------------
    # Endpoint probing – actual HTTP calls to verify auth / tunnel
    # ------------------------------------------------------------------

    # Endpoints whose POST handler enforces Bot Framework JWT auth via
    # the BotFrameworkAdapter – they return 401 when the JWT is missing
    # or invalid.
    _BOT_FRAMEWORK_PATHS = ("/api/messages",)

    # Endpoints whose POST handler validates an ACS callback token
    # (query-param ``?token=``) and optionally an ACS-signed JWT.
    # These return 401 when the token is wrong / missing.
    _ACS_AUTH_PATHS = ("/acs", "/acs/incoming", "/realtime-acs",
                       "/api/voice/acs-callback", "/api/voice/media-streaming")

    async def _probe(self, req: web.Request) -> web.Response:
        """Probe every registered endpoint with real HTTP calls.

        Three test phases per endpoint:

        1. **Admin-key probe** – unauthenticated GET to ``127.0.0.1``.
           *401* → endpoint requires the admin secret.
        2. **Tunnel probe** – GET with Cloudflare headers.
           *403* → endpoint blocked for tunnel traffic.
        3. **Framework auth probe** – for bot / ACS category endpoints
           only: an unauthenticated POST with a minimal JSON body.
           *401* → the handler's own JWT / token validation is active.

        Each endpoint gets an ``auth_type`` label:

        * ``"admin_key"``    – protected by the admin secret middleware
        * ``"bot_jwt"``      – protected by Bot Framework JWT
        * ``"acs_token"``    – protected by ACS callback token + JWT
        * ``"health"``       – unauthenticated health / info endpoint
        * ``"open"``         – no auth detected (potential concern)
        """
        cfg.reload()
        endpoints = self._collect_endpoints(req.app)
        port = cfg.admin_port
        base = f"http://127.0.0.1:{port}"
        sem = asyncio.Semaphore(20)
        timeout = ClientTimeout(total=2)

        cf_headers = {
            "cf-connecting-ip": "198.51.100.1",
            "cf-ray": "probe",
            "cf-ipcountry": "US",
        }

        # Minimal Bot Framework activity body – enough for the adapter
        # to attempt JWT validation without executing handler logic.
        _bot_probe_body = {
            "type": "message",
            "text": "",
            "channelId": "probe",
            "from": {"id": "probe"},
            "serviceUrl": "https://probe.invalid",
            "conversation": {"id": "probe"},
        }

        async def _test(session: ClientSession, ep: dict[str, Any]) -> dict[str, Any]:
            path: str = ep["path"]
            url = f"{base}{path}"
            out: dict[str, Any] = {
                **ep,
                "requires_auth": None,
                "tunnel_blocked": None,
                "auth_type": None,
                "framework_auth_ok": None,
            }
            async with sem:
                # 1. Admin-key probe – unauthenticated GET
                try:
                    async with session.get(
                        url, timeout=timeout, allow_redirects=False,
                    ) as r:
                        out["requires_auth"] = r.status == 401
                except Exception:
                    pass

                # 2. Tunnel probe – GET with CF headers
                try:
                    async with session.get(
                        url,
                        headers=cf_headers,
                        timeout=timeout,
                        allow_redirects=False,
                    ) as r:
                        out["tunnel_blocked"] = r.status == 403
                except Exception:
                    pass

                # 3. Framework auth probe – POST for bot/acs endpoints
                is_bot = any(path == p or path.startswith(p + "/")
                             for p in self._BOT_FRAMEWORK_PATHS)
                is_acs = any(path == p or path.startswith(p + "/")
                             for p in self._ACS_AUTH_PATHS)

                if is_bot:
                    try:
                        async with session.post(
                            url, json=_bot_probe_body,
                            timeout=timeout, allow_redirects=False,
                        ) as r:
                            out["framework_auth_ok"] = r.status == 401
                            out["auth_type"] = "bot_jwt" if r.status == 401 else "open"
                    except Exception:
                        out["auth_type"] = "bot_jwt"  # connection error = likely blocked
                elif is_acs:
                    try:
                        # ACS endpoints check ?token= param – omit it
                        async with session.post(
                            url, json=[{}],
                            timeout=timeout, allow_redirects=False,
                        ) as r:
                            out["framework_auth_ok"] = r.status == 401
                            out["auth_type"] = "acs_token" if r.status == 401 else "open"
                    except Exception:
                        out["auth_type"] = "acs_token"
                elif out.get("requires_auth"):
                    out["auth_type"] = "admin_key"
                elif path == "/health":
                    out["auth_type"] = "health"
                elif path.startswith("/api/auth/"):
                    out["auth_type"] = "health"
                else:
                    out["auth_type"] = "open"

            return out

        async with ClientSession() as session:
            raw = await asyncio.gather(
                *(_test(session, ep) for ep in endpoints),
                return_exceptions=True,
            )

        probed = [r for r in raw if isinstance(r, dict)]

        total = len(probed)
        auth_required = sum(1 for e in probed if e.get("requires_auth") is True)
        public_no_auth = sum(1 for e in probed if e.get("requires_auth") is False)
        tunnel_accessible = sum(
            1 for e in probed if e.get("tunnel_blocked") is False
        )
        tunnel_blocked = sum(
            1 for e in probed if e.get("tunnel_blocked") is True
        )

        # Count by auth type
        auth_type_counts: dict[str, int] = {}
        for e in probed:
            at = e.get("auth_type") or "unknown"
            auth_type_counts[at] = auth_type_counts.get(at, 0) + 1

        # Framework auth probe summary
        framework_probed = [e for e in probed if e.get("framework_auth_ok") is not None]
        framework_ok = sum(1 for e in framework_probed if e["framework_auth_ok"])
        framework_fail = len(framework_probed) - framework_ok

        return web.json_response({
            "endpoints": probed,
            "counts": {
                "total": total,
                "public_no_auth": public_no_auth,
                "auth_required": auth_required,
                "tunnel_accessible": tunnel_accessible,
                "tunnel_blocked": tunnel_blocked,
                "auth_types": auth_type_counts,
                "framework_auth_ok": framework_ok,
                "framework_auth_fail": framework_fail,
            },
            "tunnel_restricted_during_probe": cfg.tunnel_restricted,
        })

    def _collect_endpoints(self, app: web.Application) -> list[dict[str, Any]]:
        """Walk the live aiohttp router to gather all registered routes."""
        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for resource in app.router.resources():
            info = resource.get_info()
            # aiohttp resources can be plain, dynamic, or static
            path = info.get("path") or info.get("formatter") or str(resource)
            if not path or path.startswith("/{tail"):
                continue
            # Skip static asset routes
            if "/assets/" in path and info.get("directory"):
                continue

            for route in resource:
                method = route.method.upper()
                if method == "*":
                    continue
                key = (method, path)
                if key in seen:
                    continue
                seen.add(key)

                category = _classify_endpoint(method, path)
                tunnel_exposed = _is_tunnel_exposed(path)

                results.append({
                    "method": method,
                    "path": path,
                    "category": category,
                    "tunnel_exposed": tunnel_exposed,
                })

        # Sort by category then path
        results.sort(key=lambda e: (e["category"], e["path"], e["method"]))
        return results

    def _build_components(self, deploy_mode: str) -> list[dict[str, Any]]:
        """Build the list of network-connected components."""
        components: list[dict[str, Any]] = []

        # Azure OpenAI / Foundry
        aoai_endpoint = cfg.azure_openai_endpoint
        if aoai_endpoint:
            components.append({
                "name": "Azure OpenAI",
                "type": "ai",
                "endpoint": aoai_endpoint,
                "deployment": cfg.azure_openai_realtime_deployment,
                "status": "configured",
            })

        # GitHub Copilot (model backend)
        if cfg.github_token:
            components.append({
                "name": "GitHub Copilot",
                "type": "ai",
                "endpoint": "https://api.githubcopilot.com",
                "model": cfg.copilot_model,
                "status": "configured",
            })

        # ACS (Communication Services)
        if cfg.acs_connection_string:
            components.append({
                "name": "Azure Communication Services",
                "type": "communication",
                "status": "configured",
                "source_number": cfg.acs_source_number or None,
            })

        # Cloudflare Tunnel
        components.append({
            "name": "Cloudflare Tunnel",
            "type": "tunnel",
            "status": "active" if self._tunnel.is_active else "inactive",
            "url": self._tunnel.url,
            "restricted": cfg.tunnel_restricted,
        })

        # Azure Bot Service
        if cfg.bot_app_id:
            components.append({
                "name": "Azure Bot Service",
                "type": "bot",
                "status": "configured",
                "app_id": cfg.bot_app_id[:12] + "..." if cfg.bot_app_id else None,
            })

        # Foundry IQ / AI Search (check env for search endpoint)
        search_endpoint = cfg.env.read("SEARCH_ENDPOINT") or ""
        if search_endpoint:
            components.append({
                "name": "Azure AI Search",
                "type": "search",
                "endpoint": search_endpoint,
                "status": "configured",
            })

        # Storage / Data directory
        components.append({
            "name": "Local Data Store",
            "type": "storage",
            "path": str(cfg.data_dir),
            "status": "active",
            "deploy_mode": deploy_mode,
        })

        return components

    # ------------------------------------------------------------------
    # Resource network audit
    # ------------------------------------------------------------------

    async def _resource_audit(self, req: web.Request) -> web.Response:
        """Audit network configuration of Azure resources.

        Returns per-resource info: public access, firewall rules, allowed IPs,
        private endpoints, TLS settings, etc.
        """
        if not self._az:
            return web.json_response({"resources": [], "error": "Azure CLI not available"})

        resource_groups = self._collect_resource_groups()
        if not resource_groups:
            return web.json_response({"resources": []})

        resources: list[dict[str, Any]] = []
        for rg in resource_groups:
            raw = self._az.json("resource", "list", "--resource-group", rg)
            if not isinstance(raw, list):
                continue
            for r in raw:
                rtype = (r.get("type") or "").lower()
                rname = r.get("name", "")
                audit = self._audit_resource(rg, rname, rtype)
                if audit:
                    resources.append(audit)

        return web.json_response({"resources": resources})

    def _collect_resource_groups(self) -> list[str]:
        """Gather all known resource groups from config stores."""
        rgs: set[str] = set()

        # Main bot / infra resource group
        bot_rg = cfg.env.read("RESOURCE_GROUP") or ""
        if bot_rg:
            rgs.add(bot_rg)

        # Sandbox
        if self._sandbox_store:
            sb = self._sandbox_store.config
            if sb.resource_group:
                rgs.add(sb.resource_group)

        # Foundry IQ
        if self._foundry_iq_store:
            fiq = self._foundry_iq_store.config
            if fiq.resource_group:
                rgs.add(fiq.resource_group)

        # Deploy state resource group
        deploy_rg = cfg.env.read("DEPLOY_RESOURCE_GROUP") or ""
        if deploy_rg:
            rgs.add(deploy_rg)

        # Voice resource group
        voice_rg = cfg.env.read("VOICE_RESOURCE_GROUP") or ""
        if voice_rg:
            rgs.add(voice_rg)

        return list(rgs)

    def _audit_resource(self, rg: str, name: str, rtype: str) -> dict[str, Any] | None:
        """Return a network audit dict for a single Azure resource."""
        if "microsoft.storage/storageaccounts" in rtype:
            return self._audit_storage(rg, name)
        if "microsoft.keyvault/vaults" in rtype:
            return self._audit_keyvault(rg, name)
        if "microsoft.cognitiveservices/accounts" in rtype:
            return self._audit_cognitive(rg, name)
        if "microsoft.search/searchservices" in rtype:
            return self._audit_search(rg, name)
        if "microsoft.containerregistry/registries" in rtype:
            return self._audit_acr(rg, name)
        if "microsoft.app/sessionpools" in rtype:
            return self._audit_session_pool(rg, name)
        if "microsoft.communication/communicationservices" in rtype:
            return self._audit_acs(rg, name)
        return None

    def _audit_storage(self, rg: str, name: str) -> dict[str, Any] | None:
        info = self._az.json("storage", "account", "show", "--name", name, "--resource-group", rg)
        if not isinstance(info, dict):
            return None
        props = info.get("properties") or info
        net_rules = props.get("networkRuleSet") or props.get("networkAcls") or {}
        default_action = (net_rules.get("defaultAction") or "Allow")
        ip_rules = net_rules.get("ipRules") or []
        vnet_rules = net_rules.get("virtualNetworkRules") or []
        allowed_ips = [r.get("value", r.get("ipAddressOrRange", "")) for r in ip_rules]
        allowed_vnets = [r.get("id", "") for r in vnet_rules]
        public_blob = props.get("allowBlobPublicAccess", True)
        https_only = info.get("enableHttpsTrafficOnly", props.get("supportsHttpsTrafficOnly", True))
        min_tls = props.get("minimumTlsVersion", "TLS1_0")
        private_eps = self._get_private_endpoints(props)

        return {
            "name": name,
            "resource_group": rg,
            "type": "Storage Account",
            "icon": "storage",
            "public_access": default_action == "Allow",
            "default_action": default_action,
            "allowed_ips": allowed_ips,
            "allowed_vnets": allowed_vnets,
            "private_endpoints": private_eps,
            "https_only": https_only,
            "min_tls_version": min_tls,
            "extra": {
                "public_blob_access": public_blob,
            },
        }

    def _audit_keyvault(self, rg: str, name: str) -> dict[str, Any] | None:
        info = self._az.json("keyvault", "show", "--name", name, "--resource-group", rg)
        if not isinstance(info, dict):
            return None
        props = info.get("properties") or info
        net_acls = props.get("networkAcls") or {}
        default_action = (net_acls.get("defaultAction") or "Allow")
        ip_rules = net_acls.get("ipRules") or []
        vnet_rules = net_acls.get("virtualNetworkRules") or []
        allowed_ips = [r.get("value", "") for r in ip_rules]
        allowed_vnets = [r.get("id", "") for r in vnet_rules]
        public_access = props.get("publicNetworkAccess", "Enabled")
        private_eps = self._get_private_endpoints(props)
        rbac = props.get("enableRbacAuthorization", False)
        soft_delete = props.get("enableSoftDelete", False)
        purge_protect = props.get("enablePurgeProtection", False)

        return {
            "name": name,
            "resource_group": rg,
            "type": "Key Vault",
            "icon": "keyvault",
            "public_access": public_access != "Disabled" and default_action == "Allow",
            "default_action": default_action,
            "allowed_ips": allowed_ips,
            "allowed_vnets": allowed_vnets,
            "private_endpoints": private_eps,
            "extra": {
                "public_network_access": public_access,
                "rbac_authorization": rbac,
                "soft_delete": soft_delete,
                "purge_protection": purge_protect,
            },
        }

    def _audit_cognitive(self, rg: str, name: str) -> dict[str, Any] | None:
        """Audit Azure OpenAI / Cognitive Services accounts."""
        info = self._az.json(
            "cognitiveservices", "account", "show",
            "--name", name, "--resource-group", rg,
        )
        if not isinstance(info, dict):
            return None
        props = info.get("properties") or info
        net_acls = props.get("networkAcls") or {}
        default_action = (net_acls.get("defaultAction") or "Allow")
        ip_rules = net_acls.get("ipRules") or []
        vnet_rules = net_acls.get("virtualNetworkRules") or []
        allowed_ips = [r.get("value", "") for r in ip_rules]
        allowed_vnets = [r.get("id", "") for r in vnet_rules]
        public_access = props.get("publicNetworkAccess", "Enabled")
        private_eps = self._get_private_endpoints(props)
        kind = info.get("kind", "CognitiveServices")
        endpoint = props.get("endpoint") or (props.get("endpoints") or {}).get("OpenAI Language Model Instance API", "")

        label = "Azure OpenAI" if kind.lower() == "openai" else f"Cognitive Services ({kind})"

        return {
            "name": name,
            "resource_group": rg,
            "type": label,
            "icon": "ai",
            "public_access": public_access != "Disabled" and default_action == "Allow",
            "default_action": default_action,
            "allowed_ips": allowed_ips,
            "allowed_vnets": allowed_vnets,
            "private_endpoints": private_eps,
            "extra": {
                "public_network_access": public_access,
                "kind": kind,
                "endpoint": endpoint,
            },
        }

    def _audit_search(self, rg: str, name: str) -> dict[str, Any] | None:
        """Audit Azure AI Search service."""
        info = self._az.json(
            "search", "service", "show",
            "--name", name, "--resource-group", rg,
        )
        if not isinstance(info, dict):
            return None
        props = info.get("properties") or info
        public_access = props.get("publicNetworkAccess", "enabled")
        ip_rules = (props.get("networkRuleSet") or {}).get("ipRules") or []
        allowed_ips = [r.get("value", "") for r in ip_rules]
        private_eps = self._get_private_endpoints(props)

        return {
            "name": name,
            "resource_group": rg,
            "type": "Azure AI Search",
            "icon": "search",
            "public_access": public_access.lower() != "disabled",
            "default_action": "Allow" if public_access.lower() != "disabled" else "Deny",
            "allowed_ips": allowed_ips,
            "allowed_vnets": [],
            "private_endpoints": private_eps,
            "extra": {
                "public_network_access": public_access,
                "sku": info.get("sku", {}).get("name", ""),
            },
        }

    def _audit_acr(self, rg: str, name: str) -> dict[str, Any] | None:
        info = self._az.json("acr", "show", "--name", name, "--resource-group", rg)
        if not isinstance(info, dict):
            return None
        public_access = info.get("publicNetworkAccess", "Enabled")
        net_rules = info.get("networkRuleSet") or {}
        default_action = (net_rules.get("defaultAction") or "Allow")
        ip_rules = net_rules.get("ipRules") or []
        allowed_ips = [r.get("value", "") for r in ip_rules]
        admin_enabled = info.get("adminUserEnabled", False)

        return {
            "name": name,
            "resource_group": rg,
            "type": "Container Registry",
            "icon": "acr",
            "public_access": public_access == "Enabled",
            "default_action": default_action,
            "allowed_ips": allowed_ips,
            "allowed_vnets": [],
            "private_endpoints": [],
            "extra": {
                "admin_user_enabled": admin_enabled,
                "sku": info.get("sku", {}).get("name", ""),
            },
        }

    def _audit_session_pool(self, rg: str, name: str) -> dict[str, Any] | None:
        """Audit Azure Container Apps session pool."""
        return {
            "name": name,
            "resource_group": rg,
            "type": "Session Pool",
            "icon": "sandbox",
            "public_access": True,
            "default_action": "Allow",
            "allowed_ips": [],
            "allowed_vnets": [],
            "private_endpoints": [],
            "extra": {},
        }

    def _audit_acs(self, rg: str, name: str) -> dict[str, Any] | None:
        """Audit Azure Communication Services."""
        return {
            "name": name,
            "resource_group": rg,
            "type": "Communication Services",
            "icon": "communication",
            "public_access": True,
            "default_action": "Allow",
            "allowed_ips": [],
            "allowed_vnets": [],
            "private_endpoints": [],
            "extra": {},
        }

    @staticmethod
    def _get_private_endpoints(props: dict[str, Any]) -> list[str]:
        """Extract private endpoint names from a resource's properties."""
        pe_conns = props.get("privateEndpointConnections", [])
        results: list[str] = []
        for pec in pe_conns:
            pe = pec.get("privateEndpoint", {})
            pe_id = pe.get("id", "")
            if pe_id:
                # Extract just the endpoint name from the full resource ID
                results.append(pe_id.rsplit("/", 1)[-1])
        return results
