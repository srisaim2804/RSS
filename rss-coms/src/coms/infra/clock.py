"""Deterministic logical clock for reproducible event ordering."""
from __future__ import annotations

import itertools


class SimClock:
    """Monotonic logical tick source. No wall-clock → reproducible."""

    def __init__(self, start: int = 0) -> None:
        self._it = itertools.count(start)
        self._last = start

    def tick(self) -> int:
        self._last = next(self._it)
        return self._last

    @property
    def now(self) -> int:
        return self._last
