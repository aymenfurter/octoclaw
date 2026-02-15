"""Tests for sandbox helper functions and SandboxExecutor internals."""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.runtime.config.settings import cfg
from app.runtime.sandbox import (
    SandboxExecutor,
    _build_replay_command,
    _extract_command,
    _is_shell_tool,
    _parse_tool_args,
)
from app.runtime.state.sandbox_config import SandboxConfigStore


class TestIsShellTool:
    def test_terminal(self) -> None:
        assert _is_shell_tool("run_in_terminal")

    def test_shell(self) -> None:
        assert _is_shell_tool("execute_shell")

    def test_bash(self) -> None:
        assert _is_shell_tool("bash_command")

    def test_command(self) -> None:
        assert _is_shell_tool("run_command")

    def test_not_shell(self) -> None:
        assert not _is_shell_tool("read_file")

    def test_case_insensitive(self) -> None:
        assert _is_shell_tool("RunInTerminal")

    def test_unrelated(self) -> None:
        assert not _is_shell_tool("create_edit")


class TestParseToolArgs:
    def test_dict(self) -> None:
        assert _parse_tool_args({"cmd": "ls"}) == {"cmd": "ls"}

    def test_json_string(self) -> None:
        assert _parse_tool_args('{"cmd": "ls"}') == {"cmd": "ls"}

    def test_invalid_json(self) -> None:
        assert _parse_tool_args("not json") == {}

    def test_none(self) -> None:
        assert _parse_tool_args(None) == {}

    def test_int(self) -> None:
        assert _parse_tool_args(42) == {}

    def test_json_list(self) -> None:
        assert _parse_tool_args("[1, 2]") == {}


class TestExtractCommand:
    def test_from_dict_command(self) -> None:
        assert _extract_command({"command": "ls -la"}) == "ls -la"

    def test_from_dict_cmd(self) -> None:
        assert _extract_command({"cmd": "pwd"}) == "pwd"

    def test_from_dict_input(self) -> None:
        assert _extract_command({"input": "echo hi"}) == "echo hi"

    def test_from_dict_script(self) -> None:
        assert _extract_command({"script": "run.sh"}) == "run.sh"

    def test_from_string(self) -> None:
        assert _extract_command("ls -la") == "ls -la"

    def test_from_json_string(self) -> None:
        assert _extract_command('{"command": "ls"}') == "ls"

    def test_empty_dict(self) -> None:
        assert _extract_command({}) == ""

    def test_none(self) -> None:
        assert _extract_command(None) == ""


class TestBuildReplayCommand:
    def test_stdout_only(self) -> None:
        result = _build_replay_command("hello", "", True)
        assert "hello" in result

    def test_stderr_only(self) -> None:
        result = _build_replay_command("", "error", True)
        assert "error" in result
        assert ">&2" in result

    def test_both(self) -> None:
        result = _build_replay_command("out", "err", True)
        assert "out" in result
        assert "err" in result

    def test_failure(self) -> None:
        result = _build_replay_command("out", "err", False)
        assert "exit 1" in result

    def test_empty(self) -> None:
        result = _build_replay_command("", "", True)
        assert result == "true"


class TestSandboxExecutor:
    def test_enabled_property(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        executor = SandboxExecutor(config_store=store)
        assert not executor.enabled

    def test_build_bootstrap_script(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        executor = SandboxExecutor(config_store=store)
        script = executor._build_bootstrap_script("echo hello", has_data=False)
        assert "echo hello" in script
        assert "#!/bin/bash" in script
        assert "set -e" in script

    def test_build_bootstrap_with_data(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        executor = SandboxExecutor(config_store=store)
        script = executor._build_bootstrap_script("ls", has_data=True)
        assert "agent_data.zip" in script

    def test_build_bootstrap_with_env(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        executor = SandboxExecutor(config_store=store)
        script = executor._build_bootstrap_script("run", has_data=False, env_vars={"KEY": "val"})
        assert "KEY" in script
        assert "val" in script

    def test_create_data_zip_empty(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        executor = SandboxExecutor(config_store=store)
        result = executor._create_data_zip()
        assert result is None

    def test_create_data_zip_with_files(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        store.update(whitelist=["test_file.txt"])
        (data_dir / "test_file.txt").write_text("content")
        executor = SandboxExecutor(config_store=store)
        result = executor._create_data_zip()
        assert result is not None
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            assert "test_file.txt" in zf.namelist()

    def test_create_data_zip_with_dir(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        store.update(whitelist=["subdir"])
        sub = data_dir / "subdir"
        sub.mkdir()
        (sub / "file.txt").write_text("x")
        executor = SandboxExecutor(config_store=store)
        result = executor._create_data_zip()
        assert result is not None
        with zipfile.ZipFile(io.BytesIO(result)) as zf:
            names = zf.namelist()
            assert any("file.txt" in n for n in names)

    def test_merge_result_zip(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        store.update(whitelist=["merged"])
        executor = SandboxExecutor(config_store=store)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("merged/result.txt", "synced data")
        count = executor._merge_result_zip(buf.getvalue())
        assert count == 1
        assert (data_dir / "merged" / "result.txt").read_text() == "synced data"

    def test_merge_result_zip_rejects_traversal(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        store.update(whitelist=["safe"])
        executor = SandboxExecutor(config_store=store)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../escape.txt", "bad")
        count = executor._merge_result_zip(buf.getvalue())
        assert count == 0

    def test_merge_result_zip_rejects_non_whitelisted(self, data_dir: Path) -> None:
        store = SandboxConfigStore()
        store.update(whitelist=["allowed"])
        executor = SandboxExecutor(config_store=store)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("not_allowed/file.txt", "data")
        count = executor._merge_result_zip(buf.getvalue())
        assert count == 0

    def test_timing_helper(self, data_dir: Path) -> None:
        import time
        store = SandboxConfigStore()
        executor = SandboxExecutor(config_store=store)
        start = time.time()
        result = executor._timing(start, "test-id")
        assert "duration_ms" in result
        assert result["session_id"] == "test-id"
        assert isinstance(result["duration_ms"], int)

    def test_result_helper(self, data_dir: Path) -> None:
        import time
        store = SandboxConfigStore()
        executor = SandboxExecutor(config_store=store)
        start = time.time()
        result = executor._result(False, "fail reason", start, "s1")
        assert result["success"] is False
        assert result["error"] == "fail reason"
        assert result["session_id"] == "s1"
