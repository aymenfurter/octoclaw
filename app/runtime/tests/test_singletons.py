"""Tests for the singleton registry."""

from __future__ import annotations

from app.runtime.util.singletons import _reset_fns, register_singleton, reset_all_singletons


class TestSingletonRegistry:
    def setup_method(self) -> None:
        self._original = list(_reset_fns)

    def teardown_method(self) -> None:
        _reset_fns.clear()
        _reset_fns.extend(self._original)

    def test_register_adds_function(self) -> None:
        calls: list[str] = []

        def _reset() -> None:
            calls.append("called")

        register_singleton(_reset)
        assert _reset in _reset_fns

    def test_reset_all_invokes_every_resetter(self) -> None:
        calls: list[int] = []

        def _r1() -> None:
            calls.append(1)

        def _r2() -> None:
            calls.append(2)

        register_singleton(_r1)
        register_singleton(_r2)
        reset_all_singletons()
        assert 1 in calls
        assert 2 in calls
