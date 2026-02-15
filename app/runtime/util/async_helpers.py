"""Async helpers for running blocking code from an async context."""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


async def run_sync(fn: Callable[..., T], *args: object, **kwargs: object) -> T:
    """Run a blocking *fn* in the default executor without stalling the loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))
