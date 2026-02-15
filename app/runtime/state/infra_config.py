"""Infrastructure configuration store -- bot, channels, voice."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.settings import cfg

logger = logging.getLogger(__name__)


@dataclass
class BotInfraConfig:
    resource_group: str = "octoclaw-rg"
    location: str = "eastus"
    display_name: str = "octoclaw"
    bot_handle: str = ""


@dataclass
class TelegramChannelConfig:
    token: str = ""
    whitelist: str = ""


@dataclass
class VoiceCallConfig:
    acs_resource_name: str = ""
    acs_connection_string: str = ""
    acs_source_number: str = ""
    voice_target_number: str = ""
    azure_openai_resource_name: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_realtime_deployment: str = ""
    resource_group: str = ""
    voice_resource_group: str = ""
    location: str = ""


@dataclass
class ChannelsConfig:
    telegram: TelegramChannelConfig = field(default_factory=TelegramChannelConfig)
    voice_call: VoiceCallConfig = field(default_factory=VoiceCallConfig)


class InfraConfigStore:
    """Persists infrastructure configuration to ``infra.json``."""

    _SECRET_FIELDS = {"token", "acs_connection_string", "azure_openai_api_key"}

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (cfg.data_dir / "infra.json")
        self.bot = BotInfraConfig()
        self.channels = ChannelsConfig()
        self._load()

    @property
    def bot_configured(self) -> bool:
        return bool(self.bot.resource_group and self.bot.location)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.channels.telegram.token)

    @property
    def voice_call_configured(self) -> bool:
        return bool(self.channels.voice_call.acs_connection_string)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return
        bot_data = data.get("bot", {})
        for k, v in bot_data.items():
            if hasattr(self.bot, k):
                try:
                    setattr(self.bot, k, self._resolve_secret(v))
                except Exception:
                    logger.warning("Failed to resolve bot.%s -- skipping", k, exc_info=True)
        tg_data = data.get("channels", {}).get("telegram", {})
        for k, v in tg_data.items():
            if hasattr(self.channels.telegram, k):
                try:
                    setattr(self.channels.telegram, k, self._resolve_secret(v))
                except Exception:
                    logger.warning("Failed to resolve telegram.%s -- skipping", k, exc_info=True)
        vc_data = data.get("channels", {}).get("voice_call", {})
        for k, v in vc_data.items():
            if hasattr(self.channels.voice_call, k):
                try:
                    setattr(self.channels.voice_call, k, self._resolve_secret(v))
                except Exception:
                    logger.warning("Failed to resolve voice_call.%s -- skipping", k, exc_info=True)

    def _save(self) -> None:
        data = {
            "bot": asdict(self.bot),
            "channels": {
                "telegram": self._store_secrets(asdict(self.channels.telegram)),
                "voice_call": self._store_secrets(asdict(self.channels.voice_call)),
            },
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2) + "\n")

    def save_bot(self, **kwargs: str) -> None:
        for k, v in kwargs.items():
            if hasattr(self.bot, k):
                setattr(self.bot, k, v)
        self._save()

    def save_telegram(self, **kwargs: str) -> None:
        for k, v in kwargs.items():
            if hasattr(self.channels.telegram, k):
                setattr(self.channels.telegram, k, v)
        self._save()

    def clear_telegram(self) -> None:
        self.channels.telegram = TelegramChannelConfig()
        self._save()

    def save_voice_call(self, **kwargs: str) -> None:
        for k, v in kwargs.items():
            if hasattr(self.channels.voice_call, k):
                setattr(self.channels.voice_call, k, v)
        self._save()

    def clear_voice_call(self) -> None:
        self.channels.voice_call = VoiceCallConfig()
        self._save()

    def to_safe_dict(self) -> dict[str, Any]:
        data = {
            "bot": asdict(self.bot),
            "channels": {
                "telegram": self._mask_secrets(asdict(self.channels.telegram)),
                "voice_call": self._mask_secrets(asdict(self.channels.voice_call)),
            },
        }
        return data

    def _mask_secrets(self, d: dict[str, Any]) -> dict[str, Any]:
        return {
            k: ("****" if k in self._SECRET_FIELDS and v else v)
            for k, v in d.items()
        }

    def _store_secrets(self, d: dict[str, Any]) -> dict[str, Any]:
        from ..services.keyvault import kv, env_key_to_secret_name, is_kv_ref

        result = dict(d)
        if not kv.enabled:
            return result
        for k in self._SECRET_FIELDS:
            val = result.get(k, "")
            if val and not is_kv_ref(val):
                try:
                    ref = kv.store(env_key_to_secret_name(f"infra-{k}"), val)
                    result[k] = ref
                except Exception as exc:
                    logger.warning("Failed to store secret %s in KV: %s", k, exc)
        return result

    @staticmethod
    def _resolve_secret(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        from ..services.keyvault import resolve_if_kv_ref

        return resolve_if_kv_ref(value)
