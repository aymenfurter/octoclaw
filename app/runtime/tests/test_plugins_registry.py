"""Tests for the PluginRegistry module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.runtime.config.settings import cfg
from app.runtime.registries.plugins import (
    PluginManifest,
    PluginRegistry,
    _parse_manifest,
)
from app.runtime.state.plugin_config import PluginConfigStore


def _make_plugin(
    base: Path,
    plugin_id: str,
    *,
    name: str = "",
    skills: list[str] | None = None,
    default_enabled: bool = False,
    setup_skill: str = "",
) -> Path:
    d = base / plugin_id
    d.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": plugin_id,
        "name": name or plugin_id,
        "description": f"Test plugin {plugin_id}",
        "default_enabled": default_enabled,
        "setup_skill": setup_skill,
    }
    if skills is not None:
        manifest["skills"] = skills
    (d / "PLUGIN.json").write_text(json.dumps(manifest))
    return d


def _make_skill(base: Path, skill_name: str, content: str = "# Skill") -> Path:
    d = base / skill_name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(content)
    return d


class TestParseManifest:
    def test_valid_manifest(self, tmp_path: Path) -> None:
        d = tmp_path / "my-plugin"
        d.mkdir()
        (d / "PLUGIN.json").write_text(json.dumps({
            "id": "my-plugin",
            "name": "My Plugin",
            "description": "A test plugin",
            "version": "1.0.0",
        }))
        m = _parse_manifest(d / "PLUGIN.json")
        assert m is not None
        assert m.id == "my-plugin"
        assert m.name == "My Plugin"
        assert m.version == "1.0.0"

    def test_invalid_json_returns_none(self, tmp_path: Path) -> None:
        d = tmp_path / "bad"
        d.mkdir()
        (d / "PLUGIN.json").write_text("{bad")
        assert _parse_manifest(d / "PLUGIN.json") is None

    def test_auto_discovers_skills_dir(self, tmp_path: Path) -> None:
        d = tmp_path / "plugin-with-skills"
        d.mkdir()
        (d / "PLUGIN.json").write_text(json.dumps({"id": "plugin-with-skills", "name": "P"}))
        _make_skill(d / "skills", "skill-a")
        _make_skill(d / "skills", "skill-b")
        m = _parse_manifest(d / "PLUGIN.json")
        assert m is not None
        assert set(m.skills) == {"skill-a", "skill-b"}

    def test_explicit_skills_override_auto(self, tmp_path: Path) -> None:
        d = tmp_path / "explicit"
        d.mkdir()
        (d / "PLUGIN.json").write_text(json.dumps({
            "id": "explicit",
            "name": "E",
            "skills": ["only-this"],
        }))
        _make_skill(d / "skills", "other")
        m = _parse_manifest(d / "PLUGIN.json")
        assert m is not None
        assert m.skills == ["only-this"]


class TestPluginManifest:
    def test_to_dict(self) -> None:
        m = PluginManifest(id="test", name="Test Plugin", version="2.0.0")
        d = m.to_dict()
        assert d["id"] == "test"
        assert d["version"] == "2.0.0"
        assert "source_dir" not in d

    def test_defaults(self) -> None:
        m = PluginManifest(id="x", name="X")
        assert m.default_enabled is False
        assert m.skills == []
        assert m.dependencies == {}


class TestPluginRegistry:
    def test_discover_bundled(self, data_dir: Path) -> None:
        plugins_dir = cfg.project_root / "plugins"
        _make_plugin(plugins_dir, "test-plugin-a")
        _make_plugin(plugins_dir, "test-plugin-b")
        try:
            reg = PluginRegistry()
            names = {p["id"] for p in reg.list_plugins()}
            assert "test-plugin-a" in names
            assert "test-plugin-b" in names
        finally:
            import shutil
            for p in ("test-plugin-a", "test-plugin-b"):
                d = plugins_dir / p
                if d.exists():
                    shutil.rmtree(d)

    def test_discover_user_plugins(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        _make_plugin(user_plugins, "user-plugin")
        reg = PluginRegistry()
        names = {p["id"] for p in reg.list_plugins()}
        assert "user-plugin" in names

    def test_get_plugin(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        _make_plugin(user_plugins, "fetched")
        reg = PluginRegistry()
        p = reg.get_plugin("fetched")
        assert p is not None
        assert p["id"] == "fetched"
        assert p["source"] == "user"

    def test_get_plugin_not_found(self, data_dir: Path) -> None:
        reg = PluginRegistry()
        assert reg.get_plugin("nonexistent") is None

    def test_get_manifest(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        _make_plugin(user_plugins, "mfest")
        reg = PluginRegistry()
        m = reg.get_manifest("mfest")
        assert m is not None
        assert isinstance(m, PluginManifest)

    def test_enable_plugin_copies_skills(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        pd = _make_plugin(user_plugins, "with-skill", skills=["my-skill"])
        _make_skill(pd / "skills", "my-skill", "---\nname: my-skill\n---\n# Hello")
        reg = PluginRegistry()
        result = reg.enable_plugin("with-skill")
        assert result is not None
        assert result["enabled"] is True
        assert (cfg.user_skills_dir / "my-skill" / "SKILL.md").exists()

    def test_disable_plugin_removes_skills(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        pd = _make_plugin(user_plugins, "dis-plugin", skills=["rem-skill"])
        _make_skill(pd / "skills", "rem-skill")
        reg = PluginRegistry()
        reg.enable_plugin("dis-plugin")
        assert (cfg.user_skills_dir / "rem-skill").exists()
        reg.disable_plugin("dis-plugin")
        assert not (cfg.user_skills_dir / "rem-skill").exists()

    def test_enable_nonexistent_returns_none(self, data_dir: Path) -> None:
        reg = PluginRegistry()
        assert reg.enable_plugin("nope") is None

    def test_disable_nonexistent_returns_none(self, data_dir: Path) -> None:
        reg = PluginRegistry()
        assert reg.disable_plugin("nope") is None

    def test_remove_user_plugin(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        _make_plugin(user_plugins, "removable")
        reg = PluginRegistry()
        assert reg.remove_user_plugin("removable")
        assert reg.get_plugin("removable") is None

    def test_remove_nonexistent_user_plugin(self, data_dir: Path) -> None:
        reg = PluginRegistry()
        assert not reg.remove_user_plugin("nope")

    def test_refresh_rediscovers(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        reg = PluginRegistry()
        assert reg.get_plugin("late-add") is None
        _make_plugin(user_plugins, "late-add")
        reg.refresh()
        assert reg.get_plugin("late-add") is not None

    def test_complete_setup(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        pd = _make_plugin(user_plugins, "setup-plugin", setup_skill="setup-wizard")
        _make_skill(pd / "skills", "setup-wizard")
        reg = PluginRegistry()
        reg.enable_plugin("setup-plugin")
        assert (cfg.user_skills_dir / "setup-wizard").exists()
        result = reg.complete_setup("setup-plugin")
        assert result is not None
        assert result["setup_completed"] is True
        assert not (cfg.user_skills_dir / "setup-wizard").exists()

    def test_complete_setup_nonexistent(self, data_dir: Path) -> None:
        reg = PluginRegistry()
        assert reg.complete_setup("nope") is None

    def test_get_setup_skill_content(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        pd = _make_plugin(user_plugins, "sc-plugin", setup_skill="my-setup")
        _make_skill(pd / "skills", "my-setup", "Setup instructions here")
        reg = PluginRegistry()
        content = reg.get_setup_skill_content("sc-plugin")
        assert content == "Setup instructions here"

    def test_get_setup_skill_content_no_setup(self, data_dir: Path) -> None:
        user_plugins = data_dir / "plugins"
        _make_plugin(user_plugins, "no-setup-plugin")
        reg = PluginRegistry()
        assert reg.get_setup_skill_content("no-setup-plugin") is None

    def test_import_from_zip(self, data_dir: Path) -> None:
        import tempfile
        import zipfile

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            zip_path = Path(f.name)
        with zipfile.ZipFile(zip_path, "w") as zf:
            manifest = {"id": "zip-plugin", "name": "Zip Plugin", "description": "From zip"}
            zf.writestr("zip-plugin/PLUGIN.json", json.dumps(manifest))
        reg = PluginRegistry()
        result = reg.import_from_zip(zip_path)
        assert result is not None
        assert result["id"] == "zip-plugin"
        zip_path.unlink()

    def test_import_from_zip_no_manifest(self, data_dir: Path) -> None:
        import tempfile
        import zipfile

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            zip_path = Path(f.name)
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "no manifest here")
        reg = PluginRegistry()
        with pytest.raises(ValueError, match="No PLUGIN.json"):
            reg.import_from_zip(zip_path)
        zip_path.unlink()
