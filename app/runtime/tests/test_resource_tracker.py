"""Tests for ResourceTracker and data classes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.runtime.services.resource_tracker import (
    AuditResult,
    AzureResource,
    ResourceGroup,
    ResourceTracker,
)


class TestDataClasses:
    def test_azure_resource_defaults(self) -> None:
        r = AzureResource()
        assert r.id == ""
        assert r.name == ""
        assert r.resource_group == ""
        assert r.tags == {}

    def test_azure_resource_with_values(self) -> None:
        r = AzureResource(
            id="/sub/rg/res", name="myres",
            resource_group="myrg", resource_type="Microsoft.Web/sites",
            location="eastus", tags={"env": "test"}, deploy_tag="dep-1",
        )
        assert r.name == "myres"
        assert r.deploy_tag == "dep-1"

    def test_resource_group_defaults(self) -> None:
        g = ResourceGroup()
        assert g.name == ""
        assert g.location == ""

    def test_audit_result_defaults(self) -> None:
        a = AuditResult()
        assert a.tracked_resources == []
        assert a.orphaned_resources == []
        assert a.orphaned_groups == []
        assert a.known_deploy_ids == []
        assert a.unknown_deploy_ids == []


class TestResourceTrackerDiscover:
    def _make_tracker(self) -> tuple[ResourceTracker, MagicMock, MagicMock]:
        az = MagicMock()
        store = MagicMock()
        return ResourceTracker(az, store), az, store

    def test_discover_tagged_groups_empty(self) -> None:
        tracker, az, _ = self._make_tracker()
        az.json.return_value = []
        result = tracker.discover_tagged_resource_groups()
        assert result == []

    def test_discover_tagged_groups(self) -> None:
        tracker, az, _ = self._make_tracker()
        az.json.return_value = [
            {"name": "polyclaw-prod", "location": "eastus", "tags": {}},
            {"name": "other-rg", "location": "westus", "tags": {}},
            {"name": "tagged-rg", "location": "eastus", "tags": {"polyclaw_deploy": "dep-1"}},
        ]
        result = tracker.discover_tagged_resource_groups()
        assert len(result) == 2
        names = {g.name for g in result}
        assert "polyclaw-prod" in names
        assert "tagged-rg" in names
        assert "other-rg" not in names

    def test_discover_resources_in_group(self) -> None:
        tracker, az, _ = self._make_tracker()
        az.json.return_value = [
            {"id": "/sub/rg/res1", "name": "res1", "type": "Microsoft.Web/sites",
             "location": "eastus", "tags": {"polyclaw_deploy": "dep-1"}},
        ]
        result = tracker.discover_resources_in_group("myrg")
        assert len(result) == 1
        assert result[0].name == "res1"
        assert result[0].resource_group == "myrg"

    def test_discover_resources_none_result(self) -> None:
        tracker, az, _ = self._make_tracker()
        az.json.return_value = None
        result = tracker.discover_resources_in_group("rg")
        assert result == []

    def test_discover_all_polyclaw_resources(self) -> None:
        tracker, az, _ = self._make_tracker()
        az.json.return_value = [
            {
                "id": "/subscriptions/s/resourceGroups/myrg/providers/Microsoft.Web/sites/app1",
                "name": "app1", "type": "Microsoft.Web/sites",
                "location": "eastus", "tags": {"polyclaw_deploy": "dep-1"},
            }
        ]
        result = tracker.discover_all_polyclaw_resources()
        assert len(result) == 1
        assert result[0].resource_group == "myrg"


class TestResourceTrackerToDict:
    def test_to_dict(self) -> None:
        az = MagicMock()
        store = MagicMock()
        tracker = ResourceTracker(az, store)
        audit = AuditResult(
            tracked_resources=[AzureResource(id="r1", name="res1", resource_group="rg1",
                                            resource_type="type1", location="loc1", deploy_tag="d1")],
            orphaned_resources=[AzureResource(id="r2", name="orphan1")],
            orphaned_groups=[ResourceGroup(name="orph-rg", location="eastus", deploy_tag="d2")],
            known_deploy_ids=["d1"],
            unknown_deploy_ids=["d2"],
        )
        d = tracker.to_dict(audit)
        assert len(d["tracked_resources"]) == 1
        assert d["tracked_resources"][0]["name"] == "res1"
        assert len(d["orphaned_resources"]) == 1
        assert len(d["orphaned_groups"]) == 1
        assert d["orphaned_groups"][0]["name"] == "orph-rg"
        assert d["known_deploy_ids"] == ["d1"]
        assert d["unknown_deploy_ids"] == ["d2"]


class TestResourceTrackerAudit:
    def test_audit_no_groups(self) -> None:
        az = MagicMock()
        store = MagicMock()
        store.all_deployments = {}
        az.json.return_value = []
        tracker = ResourceTracker(az, store)
        result = tracker.audit()
        assert isinstance(result, AuditResult)
        assert result.tracked_resources == []
        assert result.orphaned_resources == []

    def test_audit_known_deployment(self) -> None:
        az = MagicMock()
        store = MagicMock()
        store.all_deployments = {"abc123": {"tag": "t1"}}

        def json_side_effect(*args, **kwargs):
            cmd = " ".join(args)
            if "group list" in cmd:
                return [{"name": "polyclaw-rg", "location": "eastus",
                         "tags": {"polyclaw_deploy": "polycl-abc123"}}]
            if "resource list" in cmd:
                if "--resource-group" in cmd:
                    return [{"id": "/res1", "name": "app", "type": "Web",
                             "location": "eastus", "tags": {"polyclaw_deploy": "polycl-abc123"}}]
                return []
            return []

        az.json.side_effect = json_side_effect
        tracker = ResourceTracker(az, store)
        result = tracker.audit()
        assert len(result.tracked_resources) >= 1


class TestReconcile:
    def test_no_active_deployments(self) -> None:
        az = MagicMock()
        store = MagicMock()
        store.active_deployments.return_value = []
        tracker = ResourceTracker(az, store)
        changes = tracker.reconcile()
        assert changes == []

    def test_reconcile_dead_rg(self) -> None:
        az = MagicMock()
        store = MagicMock()
        rec = MagicMock()
        rec.deploy_id = "d1"
        rec.tag = "t1"
        rec.resource_groups = ["alive-rg", "dead-rg"]
        rec.resources = []
        store.active_deployments.return_value = [rec]
        az.json.return_value = ["alive-rg"]
        tracker = ResourceTracker(az, store)
        changes = tracker.reconcile()
        assert len(changes) >= 1
        assert any(c["action"] == "pruned_rgs" for c in changes)

    def test_reconcile_all_rgs_dead(self) -> None:
        az = MagicMock()
        store = MagicMock()
        rec = MagicMock()
        rec.deploy_id = "d1"
        rec.tag = "t1"
        rec.resource_groups = ["dead-rg"]
        rec.resources = []
        store.active_deployments.return_value = [rec]
        az.json.return_value = []
        tracker = ResourceTracker(az, store)
        changes = tracker.reconcile()
        assert any(c["action"] == "removed" for c in changes)
        store.remove.assert_called_once_with("d1")


class TestCleanupDeployment:
    def test_not_found(self) -> None:
        az = MagicMock()
        store = MagicMock()
        store.get.return_value = None
        tracker = ResourceTracker(az, store)
        steps = tracker.cleanup_deployment("missing")
        assert steps[0]["status"] == "failed"

    def test_cleanup_rgs(self) -> None:
        az = MagicMock()
        az.ok.return_value = (True, "ok")
        store = MagicMock()
        rec = MagicMock()
        rec.resource_groups = ["rg1", "rg2"]
        store.get.return_value = rec
        tracker = ResourceTracker(az, store)
        steps = tracker.cleanup_deployment("d1")
        assert len(steps) >= 3  # 2 rg deletes + mark_destroyed
        store.mark_destroyed.assert_called_once_with("d1")
