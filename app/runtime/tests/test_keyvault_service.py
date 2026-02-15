"""Tests for KeyVault helper functions and client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.runtime.services.keyvault import (
    KV_REF_PREFIX,
    KeyVaultClient,
    env_key_to_secret_name,
    is_kv_ref,
    make_ref,
    resolve_if_kv_ref,
    secret_name_to_env_key,
)


class TestHelperFunctions:
    def test_is_kv_ref_valid(self):
        assert is_kv_ref("@kv:my-secret-name")
        assert is_kv_ref("@kv:SECRET123")
        assert is_kv_ref("@kv:a")

    def test_is_kv_ref_invalid(self):
        assert not is_kv_ref("not a ref")
        assert not is_kv_ref("@kv:")
        assert not is_kv_ref("kv:secret")
        assert not is_kv_ref("")
        assert not is_kv_ref("@kv:has spaces")
        assert not is_kv_ref("@kv:has_underscores")

    def test_make_ref(self):
        assert make_ref("my-secret") == "@kv:my-secret"
        assert make_ref("x").startswith(KV_REF_PREFIX)

    def test_env_key_to_secret_name(self):
        assert env_key_to_secret_name("BOT_APP_ID") == "bot-app-id"
        assert env_key_to_secret_name("SIMPLE") == "simple"
        assert env_key_to_secret_name("A_B_C") == "a-b-c"

    def test_secret_name_to_env_key(self):
        assert secret_name_to_env_key("bot-app-id") == "BOT_APP_ID"
        assert secret_name_to_env_key("simple") == "SIMPLE"
        assert secret_name_to_env_key("a-b-c") == "A_B_C"

    def test_roundtrip(self):
        original = "MY_SECRET_KEY"
        secret = env_key_to_secret_name(original)
        assert secret == "my-secret-key"
        back = secret_name_to_env_key(secret)
        assert back == original


class TestKeyVaultClient:
    def test_not_enabled_by_default(self):
        kv = KeyVaultClient()
        assert not kv.enabled
        assert kv.url is None

    def test_store_returns_value_when_disabled(self):
        kv = KeyVaultClient()
        result = kv.store("test", "plain-value")
        assert result == "plain-value"

    def test_resolve_returns_env_when_disabled(self):
        kv = KeyVaultClient()
        env = {"KEY": "value", "OTHER": "@kv:ref"}
        result = kv.resolve(env)
        assert result == env

    def test_resolve_value_when_disabled(self):
        kv = KeyVaultClient()
        assert kv.resolve_value("@kv:test") == "@kv:test"
        assert kv.resolve_value("plain") == "plain"

    def test_delete_when_disabled(self):
        kv = KeyVaultClient()
        kv.delete("test")

    def test_list_secrets_when_disabled(self):
        kv = KeyVaultClient()
        assert kv.list_secrets() == []

    def test_store_env_secret_when_disabled(self):
        kv = KeyVaultClient()
        result = kv.store_env_secret("MY_KEY", "value")
        assert result == "value"

    def test_reinit(self):
        kv = KeyVaultClient()
        kv._initialised = True
        kv._url = "https://test.vault.azure.net"
        kv.reinit()
        assert not kv._initialised
        assert kv._url is None

    @patch.dict("os.environ", {"KEY_VAULT_URL": ""})
    def test_init_no_url(self):
        kv = KeyVaultClient()
        kv._ensure_init()
        assert not kv.enabled

    def test_is_firewall_error(self):
        assert KeyVaultClient._is_firewall_error(
            Exception("ForbiddenByConnection: access denied")
        )
        assert KeyVaultClient._is_firewall_error(
            Exception("Client address is not authorized")
        )
        assert not KeyVaultClient._is_firewall_error(
            Exception("some other error")
        )


class TestResolveIfKvRef:
    def test_plain_value(self):
        result = resolve_if_kv_ref("plain-text")
        assert result == "plain-text"

    def test_kv_ref_without_vault_returns_empty(self):
        """When KV is disabled, a KV reference must NOT leak through as a raw string."""
        result = resolve_if_kv_ref("@kv:test-secret")
        assert result == ""
