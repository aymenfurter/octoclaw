"""Tests for the EnvFile helper."""

from __future__ import annotations

from pathlib import Path

from app.runtime.util.env_file import EnvFile


class TestEnvFile:
    def test_read_write_roundtrip(self, tmp_path: Path) -> None:
        env = EnvFile(tmp_path / ".env")
        env.write(FOO="bar", BAZ="qux")
        assert env.read("FOO") == "bar"
        assert env.read("BAZ") == "qux"
        assert env.read("MISSING") == ""

    def test_write_removes_empty_values(self, tmp_path: Path) -> None:
        env = EnvFile(tmp_path / ".env")
        env.write(KEY="value")
        assert env.read("KEY") == "value"
        env.write(KEY="")
        assert env.read("KEY") == ""

    def test_read_all(self, tmp_path: Path) -> None:
        env = EnvFile(tmp_path / ".env")
        env.write(A="1", B="2", C="3")
        assert env.read_all() == {"A": "1", "B": "2", "C": "3"}

    def test_handles_comments(self, tmp_path: Path) -> None:
        p = tmp_path / ".env"
        p.write_text("# comment\nKEY=val\n")
        env = EnvFile(p)
        assert env.read("KEY") == "val"
        assert len(env.read_all()) == 1

    def test_handles_quoted_values(self, tmp_path: Path) -> None:
        p = tmp_path / ".env"
        p.write_text('KEY="hello world"\n')
        env = EnvFile(p)
        assert env.read("KEY") == "hello world"

    def test_file_not_exists(self, tmp_path: Path) -> None:
        env = EnvFile(tmp_path / "nonexistent.env")
        assert env.read("ANY") == ""
        assert env.read_all() == {}
