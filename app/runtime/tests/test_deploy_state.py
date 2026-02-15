"""Tests for the DeployStateStore."""

from __future__ import annotations

from pathlib import Path

from app.runtime.state.deploy_state import (
    DeployStateStore,
    DeploymentRecord,
    ResourceEntry,
    TAG_PREFIX,
    deploy_tag,
    generate_deploy_id,
)


class TestHelpers:
    def test_generate_deploy_id(self) -> None:
        d1 = generate_deploy_id()
        d2 = generate_deploy_id()
        assert isinstance(d1, str)
        assert len(d1) == 8
        assert d1 != d2

    def test_deploy_tag(self) -> None:
        tag = deploy_tag("abcd1234")
        assert tag == f"{TAG_PREFIX}-abcd1234"


class TestDeploymentRecord:
    def test_new(self) -> None:
        rec = DeploymentRecord.new("local", deploy_id="test1234")
        assert rec.deploy_id == "test1234"
        assert rec.kind == "local"
        assert rec.status == "active"
        assert rec.tag == f"{TAG_PREFIX}-test1234"

    def test_touch(self) -> None:
        rec = DeploymentRecord.new("aca")
        old_ts = rec.updated_at
        rec.touch()
        assert rec.updated_at >= old_ts

    def test_add_resource(self) -> None:
        rec = DeploymentRecord.new("local")
        entry = rec.add_resource("Microsoft.Storage/storageAccounts", "rg1", "sa1", purpose="data")
        assert isinstance(entry, ResourceEntry)
        assert len(rec.resources) == 1
        assert "rg1" in rec.resource_groups

    def test_mark_destroyed(self) -> None:
        rec = DeploymentRecord.new("aca")
        rec.mark_destroyed()
        assert rec.status == "destroyed"

    def test_mark_stopped(self) -> None:
        rec = DeploymentRecord.new("local")
        rec.mark_stopped()
        assert rec.status == "stopped"


class TestDeployStateStore:
    def test_empty_store(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        assert store.all_deployments == {}
        assert store.active_deployments() == []

    def test_register_and_get(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        rec = DeploymentRecord.new("local", deploy_id="aaa")
        store.register(rec)
        found = store.get("aaa")
        assert found is not None
        assert found.kind == "local"

    def test_current_local(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        rec = DeploymentRecord.new("local", deploy_id="loc1")
        store.register(rec)
        assert store.current_local() is not None

    def test_current_aca(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        rec = DeploymentRecord.new("aca", deploy_id="aca1")
        store.register(rec)
        assert store.current_aca() is not None

    def test_current_local_none(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        assert store.current_local() is None

    def test_mark_destroyed(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        rec = DeploymentRecord.new("local", deploy_id="d1")
        store.register(rec)
        store.mark_destroyed("d1")
        assert store.get("d1").status == "destroyed"
        assert store.active_deployments() == []

    def test_remove(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        rec = DeploymentRecord.new("local", deploy_id="rm1")
        store.register(rec)
        assert store.remove("rm1")
        assert store.get("rm1") is None
        assert not store.remove("rm1")

    def test_by_kind(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        store.register(DeploymentRecord.new("local", deploy_id="l1"))
        store.register(DeploymentRecord.new("aca", deploy_id="a1"))
        assert len(store.by_kind("local")) == 1
        assert len(store.by_kind("aca")) == 1

    def test_summary(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        store.register(DeploymentRecord.new("local", deploy_id="s1"))
        summary = store.summary()
        assert len(summary) == 1
        assert summary[0]["deploy_id"] == "s1"

    def test_persistence(self, tmp_path: Path) -> None:
        db = tmp_path / "deploys.json"
        s1 = DeployStateStore(path=db)
        s1.register(DeploymentRecord.new("local", deploy_id="p1"))
        s2 = DeployStateStore(path=db)
        assert s2.get("p1") is not None

    def test_update(self, tmp_path: Path) -> None:
        store = DeployStateStore(path=tmp_path / "deploys.json")
        rec = DeploymentRecord.new("local", deploy_id="u1")
        store.register(rec)
        rec.add_resource("Microsoft.KeyVault/vaults", "rg1", "kv1")
        store.update(rec)
        reloaded = DeployStateStore(path=tmp_path / "deploys.json")
        assert len(reloaded.get("u1").resources) == 1
