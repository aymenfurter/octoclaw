"""Foundry IQ configuration -- Azure AI Search + embedding settings."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..config.settings import cfg

logger = logging.getLogger(__name__)


@dataclass
class FoundryIQConfig:
    enabled: bool = False
    search_endpoint: str = ""
    search_api_key: str = ""
    index_name: str = "polyclaw-memories"
    embedding_endpoint: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    index_schedule: str = "daily"
    last_indexed_at: str = ""
    resource_group: str = ""
    location: str = ""
    search_resource_name: str = ""
    openai_resource_name: str = ""
    openai_deployment_name: str = ""
    provisioned: bool = False


class FoundryIQConfigStore:
    """JSON-file-backed Foundry IQ configuration."""

    _SECRET_FIELDS = frozenset({"search_api_key", "embedding_api_key"})

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (cfg.data_dir / "foundry_iq.json")
        self._config = FoundryIQConfig()
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def config(self) -> FoundryIQConfig:
        return self._config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def is_configured(self) -> bool:
        c = self._config
        if c.provisioned:
            return bool(c.search_endpoint and c.embedding_endpoint)
        return bool(
            c.search_endpoint and c.search_api_key
            and c.embedding_endpoint and c.embedding_api_key
        )

    @property
    def is_provisioned(self) -> bool:
        return self._config.provisioned

    def to_dict(self) -> dict[str, Any]:
        return asdict(self._config)

    def to_safe_dict(self) -> dict[str, Any]:
        data = asdict(self._config)
        for key in ("search_api_key", "embedding_api_key"):
            if data.get(key):
                data[key] = "****"
        return data

    def save(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            if hasattr(self._config, k):
                if k == "enabled" and isinstance(v, str):
                    v = v.lower() in ("true", "1", "yes")
                elif k == "embedding_dimensions" and isinstance(v, str):
                    v = int(v)
                setattr(self._config, k, v)
        self._save()

    def set_last_indexed(self, timestamp: str) -> None:
        self._config.last_indexed_at = timestamp
        self._save()

    def clear_provisioning(self) -> None:
        for attr in (
            "resource_group", "location", "search_resource_name",
            "openai_resource_name", "openai_deployment_name",
            "search_endpoint", "search_api_key",
            "embedding_endpoint", "embedding_api_key",
        ):
            setattr(self._config, attr, "")
        self._config.provisioned = False
        self._config.enabled = False
        self._save()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text())
            for k in FoundryIQConfig.__dataclass_fields__:
                if k in raw:
                    value = raw[k]
                    if k in self._SECRET_FIELDS and isinstance(value, str):
                        value = self._resolve_secret(value)
                    setattr(self._config, k, value)
        except Exception as exc:
            logger.warning("Failed to load Foundry IQ config from %s: %s", self._path, exc)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self._config)
        data = self._store_secrets(data)
        self._path.write_text(json.dumps(data, indent=2) + "\n")

    def _store_secrets(self, d: dict[str, Any]) -> dict[str, Any]:
        from ..services.keyvault import kv, env_key_to_secret_name, is_kv_ref

        result = dict(d)
        if not kv.enabled:
            return result
        for k in self._SECRET_FIELDS:
            val = result.get(k, "")
            if val and not is_kv_ref(val):
                try:
                    ref = kv.store(env_key_to_secret_name(f"foundryiq-{k}"), val)
                    result[k] = ref
                except Exception as exc:
                    logger.warning("Failed to store secret %s in KV: %s", k, exc)
        return result

    @staticmethod
    def _resolve_secret(value: str) -> str:
        from ..services.keyvault import resolve_if_kv_ref
        return resolve_if_kv_ref(value)


# -- singleton -------------------------------------------------------------

_store: FoundryIQConfigStore | None = None


def get_foundry_iq_config() -> FoundryIQConfigStore:
    global _store
    if _store is None:
        _store = FoundryIQConfigStore()
    return _store


def _reset_store() -> None:
    global _store
    _store = None


from ..util.singletons import register_singleton
register_singleton(_reset_store)
