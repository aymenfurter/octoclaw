"""Tests for the JsonStore base class."""

from __future__ import annotations

import json
from pathlib import Path

from app.runtime.state._json_store import JsonStore


class TestJsonStore:
    def test_load_nonexistent_returns_default_dict(self, tmp_path: Path) -> None:
        store = JsonStore(tmp_path / "missing.json")
        assert store.load() == {}

    def test_load_nonexistent_returns_custom_default(self, tmp_path: Path) -> None:
        store = JsonStore(tmp_path / "missing.json", default=[])
        assert store.load() == []

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        store = JsonStore(path)
        store.save({"key": "value", "count": 42})
        assert store.load() == {"key": "value", "count": 42}

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "store.json"
        store = JsonStore(path)
        store.save({"ok": True})
        assert path.exists()
        assert store.load() == {"ok": True}

    def test_load_corrupt_json_returns_default(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.json"
        path.write_text("{bad json!!!")
        store = JsonStore(path)
        assert store.load() == {}

    def test_load_corrupt_json_with_list_default(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.json"
        path.write_text("not json")
        store = JsonStore(path, default=[])
        assert store.load() == []

    def test_save_list_data(self, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        store = JsonStore(path, default=[])
        store.save([1, 2, 3])
        assert store.load() == [1, 2, 3]

    def test_default_copy_returns_independent_copies(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.json"
        store = JsonStore(path, default={"key": "val"})
        a = store.load()
        b = store.load()
        a["extra"] = 1
        assert "extra" not in b

    def test_path_property(self, tmp_path: Path) -> None:
        path = tmp_path / "store.json"
        store = JsonStore(path)
        assert store.path == path

    def test_scalar_default(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.json"
        store = JsonStore(path, default=0)
        assert store.load() == 0

    def test_save_with_non_serializable_uses_str(self, tmp_path: Path) -> None:
        path = tmp_path / "dates.json"
        store = JsonStore(path)
        from datetime import datetime, UTC
        store.save({"ts": datetime(2025, 1, 1, tzinfo=UTC)})
        raw = json.loads(path.read_text())
        assert isinstance(raw["ts"], str)
