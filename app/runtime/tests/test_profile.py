"""Tests for the profile module."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.runtime.state.profile import (
    get_full_profile,
    increment_skill_usage,
    load_profile,
    load_skill_usage,
    log_interaction,
    save_profile,
)


class TestProfile:
    def test_load_default(self, data_dir: Path) -> None:
        profile = load_profile()
        assert profile["name"] == "polyclaw"
        assert profile["emotional_state"] == "neutral"

    def test_save_and_load(self, data_dir: Path) -> None:
        profile = load_profile()
        profile["name"] = "TestBot"
        save_profile(profile)
        loaded = load_profile()
        assert loaded["name"] == "TestBot"

    def test_defaults_preserved(self, data_dir: Path) -> None:
        save_profile({"name": "X"})
        loaded = load_profile()
        assert loaded["name"] == "X"
        assert "emotional_state" in loaded

    def test_corrupt_json_returns_default(self, data_dir: Path) -> None:
        path = data_dir / "agent_profile.json"
        path.write_text("NOT JSON")
        profile = load_profile()
        assert profile["name"] == "polyclaw"


class TestSkillUsage:
    def test_empty_usage(self, data_dir: Path) -> None:
        assert load_skill_usage() == {}

    def test_increment(self, data_dir: Path) -> None:
        increment_skill_usage("web-search")
        increment_skill_usage("web-search")
        increment_skill_usage("note-taking")
        usage = load_skill_usage()
        assert usage["web-search"] == 2
        assert usage["note-taking"] == 1


class TestInteractionLog:
    def test_log_interaction(self, data_dir: Path) -> None:
        log_interaction("chat", channel="web")
        log_interaction("chat", channel="telegram")
        path = data_dir / "interactions.json"
        assert path.exists()

    @pytest.mark.slow
    def test_log_caps_at_1000(self, data_dir: Path) -> None:
        import json

        for i in range(1010):
            log_interaction("chat", channel="web")
        interactions = json.loads((data_dir / "interactions.json").read_text())
        assert len(interactions) == 1000


class TestFullProfile:
    def test_merges_usage(self, data_dir: Path) -> None:
        increment_skill_usage("test-skill")
        full = get_full_profile()
        assert "skill_usage" in full
        assert full["skill_usage"]["test-skill"] == 1
