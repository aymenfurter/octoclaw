"""Shared pytest fixtures for app.runtime tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("OCTOCLAW_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OCTOCLAW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOTENV_PATH", str(tmp_path / ".env"))
    return data_dir


@pytest.fixture(autouse=True)
def _reset_singletons(_isolate_data_dir: Path):
    from app.runtime.util.singletons import reset_all_singletons

    reset_all_singletons()
    yield
    reset_all_singletons()


@pytest.fixture()
def data_dir(_isolate_data_dir: Path) -> Path:
    return _isolate_data_dir


@pytest.fixture()
def mock_agent() -> AsyncMock:
    agent = AsyncMock()
    agent.has_session = True
    agent.request_counts = {}
    agent.send.return_value = "mock response"
    return agent
