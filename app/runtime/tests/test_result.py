"""Tests for the Result type."""

from __future__ import annotations

import pytest

from app.runtime.util.result import Result


class TestResultOk:
    def test_truthiness(self) -> None:
        r = Result.ok("done")
        assert r
        assert r.success is True

    def test_message(self) -> None:
        assert Result.ok("all good").message == "all good"

    def test_default_message(self) -> None:
        assert Result.ok().message == ""

    def test_value_payload(self) -> None:
        r = Result.ok("url", value="https://example.com")
        assert r.value == "https://example.com"

    def test_value_defaults_to_none(self) -> None:
        assert Result.ok("no payload").value is None


class TestResultFail:
    def test_falsy(self) -> None:
        r = Result.fail("boom")
        assert not r
        assert r.success is False

    def test_message(self) -> None:
        assert Result.fail("broke").message == "broke"

    def test_value_always_none(self) -> None:
        assert Result.fail("err").value is None


class TestResultUnpacking:
    def test_ok_unpacking(self) -> None:
        ok, msg = Result.ok("yep")
        assert ok is True
        assert msg == "yep"

    def test_fail_unpacking(self) -> None:
        ok, msg = Result.fail("nope")
        assert ok is False
        assert msg == "nope"


class TestResultRepr:
    def test_ok_repr(self) -> None:
        r = Result.ok("done")
        assert "OK" in repr(r) or "True" in repr(r)

    def test_fail_repr(self) -> None:
        r = Result.fail("oops")
        assert "FAIL" in repr(r) or "False" in repr(r)


class TestResultFrozen:
    def test_immutable(self) -> None:
        r = Result.ok("x")
        with pytest.raises(AttributeError):
            r.success = False  # type: ignore[misc]
