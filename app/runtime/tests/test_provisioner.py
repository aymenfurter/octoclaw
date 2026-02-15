"""Tests for Provisioner and tunnel/endpoint sync."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.runtime.config.settings import cfg
from app.runtime.services.provisioner import Provisioner
from app.runtime.state.deploy_state import DeployStateStore
from app.runtime.state.infra_config import InfraConfigStore
from app.runtime.util.result import Result


@pytest.fixture()
def az() -> MagicMock:
    mock = MagicMock()
    mock.ok.return_value = (True, "ok")
    mock.json.return_value = None
    mock.update_endpoint.return_value = Result.ok("Endpoint updated")
    mock.validate_telegram_token.return_value = (True, "valid")
    mock.configure_telegram.return_value = (True, "configured")
    mock.last_stderr = ""
    return mock


@pytest.fixture()
def deployer() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def tunnel() -> MagicMock:
    mock = MagicMock()
    mock.is_active = False
    mock.url = None
    return mock


@pytest.fixture()
def store(data_dir) -> InfraConfigStore:
    return InfraConfigStore()


@pytest.fixture()
def deploy_store(data_dir) -> DeployStateStore:
    return DeployStateStore()


@pytest.fixture()
def provisioner(az, deployer, tunnel, store, deploy_store) -> Provisioner:
    return Provisioner(az, deployer, tunnel, store, deploy_store)


class TestEnsureTunnel:
    """Verify _ensure_tunnel behaviour."""

    def test_starts_new_tunnel(self, provisioner, tunnel):
        tunnel.is_active = False
        tunnel.start.return_value = Result.ok("started", value="https://new.trycloudflare.com")

        steps: list[dict] = []
        url = provisioner._ensure_tunnel(steps)

        assert url == "https://new.trycloudflare.com"
        assert steps[0]["step"] == "tunnel"
        assert steps[0]["status"] == "ok"

    def test_reuses_active_tunnel(self, provisioner, tunnel):
        """When tunnel is already active, return its URL without persisting."""
        tunnel.is_active = True
        tunnel.url = "https://active.trycloudflare.com"

        steps: list[dict] = []
        url = provisioner._ensure_tunnel(steps)

        assert url == "https://active.trycloudflare.com"
        tunnel.start.assert_not_called()

    def test_returns_none_on_failure(self, provisioner, tunnel):
        tunnel.is_active = False
        tunnel.start.return_value = Result.fail("cloudflared not found")

        steps: list[dict] = []
        url = provisioner._ensure_tunnel(steps)

        assert url is None
        assert steps[0]["status"] == "failed"


class TestEnsureBot:
    """Verify _ensure_bot always deletes existing bot and deploys fresh."""

    def test_deletes_existing_bot_before_deploying(self, provisioner, az, deployer, data_dir):
        """Even when a bot exists, it must be deleted and redeployed from scratch."""
        cfg.write_env(BOT_NAME="my-bot", BOT_RESOURCE_GROUP="my-rg")
        deployer.delete.return_value = MagicMock(ok=True, steps=[])
        deployer.deploy.return_value = MagicMock(ok=True, steps=[], bot_handle="new-bot", error="")
        az.update_endpoint.return_value = Result.ok("Endpoint updated")
        bc = MagicMock(resource_group="my-rg", location="eastus", display_name="oct", bot_handle="")

        steps: list[dict] = []
        result = provisioner._ensure_bot(bc, "https://new.trycloudflare.com", steps)

        assert result is True
        deployer.delete.assert_called_once()
        deployer.deploy.assert_called_once()
        assert any(s["step"] == "bot_cleanup" and s["status"] == "ok" for s in steps)
        assert any(s["step"] == "bot_deploy" and s["status"] == "ok" for s in steps)

    def test_deploys_when_no_existing_bot(self, provisioner, az, deployer, data_dir):
        cfg.write_env(BOT_NAME="", BOT_RESOURCE_GROUP="")  # ensure clean state
        deploy_result = MagicMock(ok=True, steps=[], bot_handle="new-bot", error="")
        deployer.deploy.return_value = deploy_result
        az.update_endpoint.return_value = Result.ok("Endpoint updated")
        bc = MagicMock(resource_group="my-rg", location="eastus", display_name="oct", bot_handle="")

        steps: list[dict] = []
        result = provisioner._ensure_bot(bc, "https://new.trycloudflare.com", steps)

        assert result is True
        deployer.delete.assert_not_called()
        deployer.deploy.assert_called_once()


class TestProvision:
    """Full provision flow."""

    def test_skips_when_not_configured(self, provisioner, store):
        store.bot = MagicMock()
        store.bot.resource_group = ""
        store.bot.location = ""

        # bot_configured returns False when rg/location are empty
        with patch.object(type(store), "bot_configured", new_callable=lambda: property(lambda self: False)):
            steps = provisioner.provision()
            assert any(s["step"] == "bot_config" and s["status"] == "skip" for s in steps)

    def test_full_provision_with_existing_bot(self, provisioner, tunnel, az, deployer, data_dir):
        """Tunnel starts -> existing bot deleted -> fresh deploy -> channels configured."""
        tunnel.is_active = False
        tunnel.start.return_value = Result.ok("started", value="https://fresh.trycloudflare.com")
        cfg.write_env(BOT_NAME="my-bot", BOT_RESOURCE_GROUP="my-rg")
        deployer.delete.return_value = MagicMock(ok=True, steps=[])
        deployer.deploy.return_value = MagicMock(ok=True, steps=[], bot_handle="new-bot", error="")
        az.update_endpoint.return_value = Result.ok("Endpoint updated")

        steps = provisioner.provision()

        tunnel_steps = [s for s in steps if s["step"] == "tunnel"]
        assert tunnel_steps[0]["status"] == "ok"
        deployer.delete.assert_called_once()
        deployer.deploy.assert_called_once()
