"""Tests for the SkillRegistry module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.runtime.config.settings import cfg
from app.runtime.registries.skills import (
    SkillInfo,
    SkillRegistry,
    _determine_origin,
    _parse_frontmatter,
)


class TestParseFrontmatter:
    def test_basic_frontmatter(self) -> None:
        text = "---\nname: my-skill\ndescription: Does stuff\n---\n# Content"
        result = _parse_frontmatter(text)
        assert result["name"] == "my-skill"
        assert result["description"] == "Does stuff"

    def test_no_frontmatter(self) -> None:
        assert _parse_frontmatter("# Just a heading") == {}

    def test_empty_string(self) -> None:
        assert _parse_frontmatter("") == {}

    def test_quoted_values(self) -> None:
        text = "---\nname: 'quoted-name'\ndescription: \"double quoted\"\n---\n"
        result = _parse_frontmatter(text)
        assert result["name"] == "quoted-name"
        assert result["description"] == "double quoted"

    def test_multiline_frontmatter(self) -> None:
        text = "---\nname: test\nauthor: Alice\nversion: 1.0\n---\nBody"
        result = _parse_frontmatter(text)
        assert result["name"] == "test"
        assert result["author"] == "Alice"
        assert result["version"] == "1.0"


class TestDetermineOrigin:
    def test_origin_file(self, tmp_path: Path) -> None:
        d = tmp_path / "skill-a"
        d.mkdir()
        (d / ".origin").write_text(json.dumps({"origin": "marketplace"}))
        assert _determine_origin(d, set(), set()) == "marketplace"

    def test_origin_file_invalid_json(self, tmp_path: Path) -> None:
        d = tmp_path / "skill-b"
        d.mkdir()
        (d / ".origin").write_text("bad json")
        assert _determine_origin(d, set(), set()) == "marketplace"

    def test_plugin_origin(self, tmp_path: Path) -> None:
        d = tmp_path / "plugin-skill"
        d.mkdir()
        assert _determine_origin(d, set(), {"plugin-skill"}) == "plugin"

    def test_builtin_origin(self, tmp_path: Path) -> None:
        d = tmp_path / "builtin-skill"
        d.mkdir()
        assert _determine_origin(d, {"builtin-skill"}, set()) == "built-in"

    def test_agent_created(self, tmp_path: Path) -> None:
        d = tmp_path / "new-skill"
        d.mkdir()
        assert _determine_origin(d, set(), set()) == "agent-created"


class TestSkillInfo:
    def test_to_dict(self) -> None:
        info = SkillInfo(
            name="test",
            description="A test skill",
            source="local",
            installed=True,
            recommended=True,
        )
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["installed"] is True
        assert d["recommended"] is True
        assert "repo_owner" not in d
        assert "repo_name" not in d

    def test_defaults(self) -> None:
        info = SkillInfo(name="x")
        assert info.description == ""
        assert info.installed is False
        assert info.edit_count == 0
        assert info.origin == ""


class TestSkillRegistry:
    def test_list_installed_empty(self, data_dir: Path) -> None:
        reg = SkillRegistry()
        assert reg.list_installed() == []

    def test_list_installed_with_skills(self, data_dir: Path) -> None:
        skills_dir = cfg.user_skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)
        d = skills_dir / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: my-skill\ndescription: Test\n---\n# Content")
        reg = SkillRegistry()
        installed = reg.list_installed()
        assert len(installed) == 1
        assert installed[0].name == "my-skill"
        assert installed[0].installed is True

    def test_get_installed(self, data_dir: Path) -> None:
        skills_dir = cfg.user_skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)
        d = skills_dir / "get-test"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: get-test\n---\n")
        reg = SkillRegistry()
        found = reg.get_installed("get-test")
        assert found is not None
        assert found.name == "get-test"

    def test_get_installed_not_found(self, data_dir: Path) -> None:
        reg = SkillRegistry()
        assert reg.get_installed("nope") is None

    def test_remove_skill(self, data_dir: Path) -> None:
        skills_dir = cfg.user_skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)
        d = skills_dir / "removable"
        d.mkdir()
        (d / "SKILL.md").write_text("# sk")
        reg = SkillRegistry()
        assert reg.remove("removable")
        assert not d.exists()

    def test_remove_nonexistent(self, data_dir: Path) -> None:
        reg = SkillRegistry()
        assert not reg.remove("no-such-skill")

    def test_get_skill_content(self, data_dir: Path) -> None:
        skills_dir = cfg.user_skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)
        d = skills_dir / "readable"
        d.mkdir()
        (d / "SKILL.md").write_text("My skill content")
        reg = SkillRegistry()
        assert reg.get_skill_content("readable") == "My skill content"

    def test_get_skill_content_missing(self, data_dir: Path) -> None:
        reg = SkillRegistry()
        assert reg.get_skill_content("missing") is None

    def test_builtin_skill_origin(self, data_dir: Path) -> None:
        import shutil

        builtin = cfg.builtin_skills_dir
        builtin.mkdir(parents=True, exist_ok=True)
        bd = builtin / "builtin-sk"
        bd.mkdir(exist_ok=True)
        (bd / "SKILL.md").write_text("# built-in")
        try:
            user = cfg.user_skills_dir
            user.mkdir(parents=True, exist_ok=True)
            ud = user / "builtin-sk"
            ud.mkdir(exist_ok=True)
            (ud / "SKILL.md").write_text("---\nname: builtin-sk\n---\n")
            reg = SkillRegistry()
            installed = reg.list_installed()
            assert len(installed) == 1
            assert installed[0].origin == "built-in"
        finally:
            shutil.rmtree(bd, ignore_errors=True)

    def test_curated_skills_recommended(self, data_dir: Path) -> None:
        skills_dir = cfg.user_skills_dir
        skills_dir.mkdir(parents=True, exist_ok=True)
        d = skills_dir / "web-search"
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: web-search\n---\n")
        reg = SkillRegistry()
        installed = reg.list_installed()
        ws = next(s for s in installed if s.name == "web-search")
        assert ws.recommended is True
