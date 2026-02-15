"""Lightweight result type for operation outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Result:
    """Represents the outcome of an operation.

    Supports boolean evaluation, tuple unpacking, and carries an optional
    payload via *value*.

    Examples::

        r = Result.ok("done")
        if r:
            print(r.message)

        ok, msg = Result.fail("boom")
    """

    success: bool
    message: str = ""
    value: Any = field(default=None, repr=False)

    # -- constructors ------------------------------------------------------

    @classmethod
    def ok(cls, message: str = "", *, value: Any = None) -> Result:
        return cls(success=True, message=message, value=value)

    @classmethod
    def fail(cls, message: str = "") -> Result:
        return cls(success=False, message=message)

    # -- protocols ---------------------------------------------------------

    def __bool__(self) -> bool:
        return self.success

    def __iter__(self):
        yield self.success
        yield self.message
