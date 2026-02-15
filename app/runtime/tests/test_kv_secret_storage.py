"""Tests for Key Vault integration in Settings.write_env and FoundryIQConfigStore.

Ensures that secrets are stored via Key Vault references (@kv:...) instead
of plaintext, and that they are resolved on read.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.runtime.config.settings import SECRET_ENV_KEYS


class TestAdminSecretInSecretKeys:
    """ADMIN_SECRET must be treated as a secret."""

    def test_admin_secret_in_secret_keys(self) -> None:
        assert "ADMIN_SECRET" in SECRET_ENV_KEYS

    def test_bot_app_password_in_secret_keys(self) -> None:
        assert "BOT_APP_PASSWORD" in SECRET_ENV_KEYS


class TestWriteEnvSecretViaKV:
    """Settings.write_env() must store secret values through Key Vault."""

    @patch("app.runtime.services.keyvault.kv")
    def test_write_env_stores_secret_via_kv(self, mock_kv, tmp_path: Path) -> None:
        from app.runtime.config.settings import cfg

        mock_kv.enabled = True
        mock_kv.store.return_value = "@kv:bot-app-password"

        cfg.write_env(BOT_APP_PASSWORD="super-secret-pw")

        mock_kv.store.assert_called_once_with("bot-app-password", "super-secret-pw")
        # The env file should contain the KV reference, not the plaintext
        assert cfg.env.read("BOT_APP_PASSWORD") == "@kv:bot-app-password"

    @patch("app.runtime.services.keyvault.kv")
    def test_write_env_stores_admin_secret_via_kv(self, mock_kv, tmp_path: Path) -> None:
        from app.runtime.config.settings import cfg

        mock_kv.enabled = True
        mock_kv.store.return_value = "@kv:admin-secret"

        cfg.write_env(ADMIN_SECRET="my-admin-key")

        mock_kv.store.assert_called_once_with("admin-secret", "my-admin-key")
        assert cfg.env.read("ADMIN_SECRET") == "@kv:admin-secret"

    @patch("app.runtime.services.keyvault.kv")
    def test_write_env_skips_non_secrets(self, mock_kv, tmp_path: Path) -> None:
        from app.runtime.config.settings import cfg

        mock_kv.enabled = True

        cfg.write_env(BOT_NAME="my-bot", BOT_RESOURCE_GROUP="my-rg")

        mock_kv.store.assert_not_called()
        assert cfg.env.read("BOT_NAME") == "my-bot"

    @patch("app.runtime.services.keyvault.kv")
    def test_write_env_skips_already_kv_ref(self, mock_kv, tmp_path: Path) -> None:
        from app.runtime.config.settings import cfg

        mock_kv.enabled = True

        cfg.write_env(BOT_APP_PASSWORD="@kv:bot-app-password")

        mock_kv.store.assert_not_called()
        assert cfg.env.read("BOT_APP_PASSWORD") == "@kv:bot-app-password"

    @patch("app.runtime.services.keyvault.kv")
    def test_write_env_falls_back_on_kv_error(self, mock_kv, tmp_path: Path) -> None:
        from app.runtime.config.settings import cfg

        mock_kv.enabled = True
        mock_kv.store.side_effect = Exception("KV unreachable")

        cfg.write_env(BOT_APP_PASSWORD="fallback-pw")

        # Should still write the plaintext as a fallback
        assert cfg.env.read("BOT_APP_PASSWORD") == "fallback-pw"

    def test_write_env_plaintext_when_kv_disabled(self, tmp_path: Path) -> None:
        from app.runtime.config.settings import cfg

        # KV is not configured by default in tests
        cfg.write_env(BOT_APP_PASSWORD="plain")
        assert cfg.env.read("BOT_APP_PASSWORD") == "plain"


class TestReadResolvesKVRef:
    """Settings._read must resolve @kv: references for secret keys."""

    @patch("app.runtime.services.keyvault.resolve_if_kv_ref")
    def test_read_resolves_kv_ref_for_secret(self, mock_resolve, tmp_path: Path) -> None:
        from app.runtime.config.settings import cfg

        cfg.env.write(BOT_APP_PASSWORD="@kv:bot-app-password")
        mock_resolve.return_value = "resolved-password"

        result = cfg._read("BOT_APP_PASSWORD")

        mock_resolve.assert_called_once_with("@kv:bot-app-password")
        assert result == "resolved-password"

    @patch("app.runtime.services.keyvault.resolve_if_kv_ref")
    def test_read_does_not_resolve_non_secret(self, mock_resolve, tmp_path: Path) -> None:
        from app.runtime.config.settings import cfg

        cfg.env.write(BOT_NAME="my-bot")

        result = cfg._read("BOT_NAME")

        mock_resolve.assert_not_called()
        assert result == "my-bot"


class TestFoundryIQKVSecrets:
    """FoundryIQConfigStore must store/load API keys through Key Vault."""

    @patch("app.runtime.services.keyvault.kv")
    def test_save_stores_api_keys_via_kv(self, mock_kv, tmp_path: Path) -> None:
        from app.runtime.state.foundry_iq_config import FoundryIQConfigStore

        mock_kv.enabled = True
        mock_kv.store.side_effect = lambda name, val: f"@kv:{name}"

        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        store.save(
            search_api_key="search-key-plain",
            embedding_api_key="embed-key-plain",
        )

        # KV store should be called for both API key fields
        assert mock_kv.store.call_count == 2

        # The JSON file should contain KV references, not plaintext
        import json
        raw = json.loads((tmp_path / "fiq.json").read_text())
        assert raw["search_api_key"].startswith("@kv:")
        assert raw["embedding_api_key"].startswith("@kv:")

    @patch("app.runtime.services.keyvault.resolve_if_kv_ref")
    def test_load_resolves_api_keys(self, mock_resolve, tmp_path: Path) -> None:
        import json

        mock_resolve.side_effect = lambda v: "resolved-" + v.split(":")[-1] if v.startswith("@kv:") else v

        fiq_path = tmp_path / "fiq.json"
        fiq_path.write_text(json.dumps({
            "enabled": True,
            "search_endpoint": "https://search.example.com",
            "search_api_key": "@kv:foundryiq-search-api-key",
            "embedding_endpoint": "https://embed.example.com",
            "embedding_api_key": "@kv:foundryiq-embedding-api-key",
        }))

        from app.runtime.state.foundry_iq_config import FoundryIQConfigStore
        store = FoundryIQConfigStore(path=fiq_path)

        assert store.config.search_api_key == "resolved-foundryiq-search-api-key"
        assert store.config.embedding_api_key == "resolved-foundryiq-embedding-api-key"

    @patch("app.runtime.services.keyvault.kv")
    def test_save_skips_kv_when_disabled(self, mock_kv, tmp_path: Path) -> None:
        from app.runtime.state.foundry_iq_config import FoundryIQConfigStore

        mock_kv.enabled = False

        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        store.save(search_api_key="plain-key")

        mock_kv.store.assert_not_called()

    @patch("app.runtime.services.keyvault.kv")
    def test_non_secret_fields_not_stored_in_kv(self, mock_kv, tmp_path: Path) -> None:
        from app.runtime.state.foundry_iq_config import FoundryIQConfigStore

        mock_kv.enabled = True

        store = FoundryIQConfigStore(path=tmp_path / "fiq.json")
        store.save(search_endpoint="https://search.example.com", index_name="my-index")

        mock_kv.store.assert_not_called()
