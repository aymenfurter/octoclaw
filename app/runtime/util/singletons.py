"""Singleton registry for test isolation."""

from __future__ import annotations

from collections.abc import Callable

_reset_fns: list[Callable[[], None]] = []


def register_singleton(reset_fn: Callable[[], None]) -> None:
    """Register a reset function to be called during test teardown."""
    _reset_fns.append(reset_fn)


def reset_all_singletons() -> None:
    """Reset every registered singleton -- intended for test isolation."""
    for fn in _reset_fns:
        fn()
