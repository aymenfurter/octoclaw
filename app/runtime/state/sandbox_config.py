"""Sandbox configuration -- whitelist/blacklist and session pool metadata."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.settings import cfg

logger = logging.getLogger(__name__)

DEFAULT_WHITELIST: list[str] = [
    "media", "memory", "notes", "sessions", "skills",
    ".copilot", ".env", ".workiq.json", "agent_profile.json",
    "conversation_refs.json", "infra.json", "interaction_log.json",
    "mcp_servers.json", "plugins.json", "scheduler.json",
    "skill_usage.json", "SOUL.md",
]

BLACKLIST: frozenset[str] = frozenset({
    ".azure", ".cache", ".config", ".IdentityService",
    ".net", ".npm", ".pki",
})


@dataclass
class SandboxConfig:
    enabled: bool = False
    sync_data: bool = True
    session_pool_endpoint: str = ""
    whitelist: list[str] = field(default_factory=lambda: list(DEFAULT_WHITELIST))
    resource_group: str = ""
    location: str = ""
    pool_name: str = ""
    pool_id: str = ""


class SandboxConfigStore:
    """JSON-file-backed sandbox configuration."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (cfg.data_dir / "sandbox.json")
        self._config = SandboxConfig()
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def config(self) -> SandboxConfig:
        return self._config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def sync_data(self) -> bool:
        return self._config.sync_data

    @property
    def session_pool_endpoint(self) -> str:
        return self._config.session_pool_endpoint

    @property
    def whitelist(self) -> list[str]:
        return list(self._config.whitelist)

    @property
    def resource_group(self) -> str:
        return self._config.resource_group

    @property
    def location(self) -> str:
        return self._config.location

    @property
    def pool_name(self) -> str:
        return self._config.pool_name

    @property
    def pool_id(self) -> str:
        return self._config.pool_id

    @property
    def is_provisioned(self) -> bool:
        return bool(self._config.pool_name and self._config.session_pool_endpoint)

    def set_enabled(self, enabled: bool) -> None:
        self._config.enabled = enabled
        self._save()

    def set_sync_data(self, sync_data: bool) -> None:
        self._config.sync_data = sync_data
        self._save()

    def set_session_pool_endpoint(self, endpoint: str) -> None:
        self._config.session_pool_endpoint = endpoint.rstrip("/")
        self._save()

    def set_whitelist(self, whitelist: list[str]) -> None:
        self._config.whitelist = [w for w in whitelist if w not in BLACKLIST]
        self._save()

    def add_whitelist_item(self, item: str) -> bool:
        if item in BLACKLIST:
            return False
        if item not in self._config.whitelist:
            self._config.whitelist.append(item)
            self._save()
        return True

    def remove_whitelist_item(self, item: str) -> None:
        if item in self._config.whitelist:
            self._config.whitelist.remove(item)
            self._save()

    def reset_whitelist(self) -> None:
        self._config.whitelist = list(DEFAULT_WHITELIST)
        self._save()

    def set_pool_metadata(
        self,
        *,
        resource_group: str,
        location: str,
        pool_name: str,
        pool_id: str,
        endpoint: str,
    ) -> None:
        self._config.resource_group = resource_group
        self._config.location = location
        self._config.pool_name = pool_name
        self._config.pool_id = pool_id
        self._config.session_pool_endpoint = endpoint.rstrip("/")
        self._save()

    def clear_pool_metadata(self) -> None:
        self._config.resource_group = ""
        self._config.location = ""
        self._config.pool_name = ""
        self._config.pool_id = ""
        self._config.session_pool_endpoint = ""
        self._save()

    def update(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if k == "whitelist":
                self.set_whitelist(v)
            elif hasattr(self._config, k):
                setattr(self._config, k, v)
        self._save()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self._config)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
            self._config = SandboxConfig(
                enabled=raw.get("enabled", False),
                sync_data=raw.get("sync_data", True),
                session_pool_endpoint=raw.get("session_pool_endpoint", ""),
                whitelist=raw.get("whitelist", list(DEFAULT_WHITELIST)),
                resource_group=raw.get("resource_group", ""),
                location=raw.get("location", ""),
                pool_name=raw.get("pool_name", ""),
                pool_id=raw.get("pool_id", ""),
            )
        except Exception as exc:
            logger.warning("Failed to load sandbox config from %s: %s", self._path, exc)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(asdict(self._config), indent=2) + "\n")
