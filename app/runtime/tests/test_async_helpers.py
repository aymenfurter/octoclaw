"""Tests for async_helpers."""

from __future__ import annotations

import pytest

from app.runtime.util.async_helpers import run_sync


@pytest.mark.asyncio
async def test_run_sync_basic() -> None:
    def add(a: int, b: int) -> int:
        return a + b

    result = await run_sync(add, 2, 3)
    assert result == 5


@pytest.mark.asyncio
async def test_run_sync_kwargs() -> None:
    def greet(name: str, prefix: str = "Hello") -> str:
        return f"{prefix}, {name}"

    result = await run_sync(greet, "World", prefix="Hi")
    assert result == "Hi, World"


@pytest.mark.asyncio
async def test_run_sync_exception() -> None:
    def boom() -> None:
        raise ValueError("fail")

    with pytest.raises(ValueError, match="fail"):
        await run_sync(boom)
