"""Correlation primitives for the cross-party event log."""
from __future__ import annotations

import itertools
from dataclasses import dataclass

_counter = itertools.count(1)


def new_correlation_id(prefix: str = "R") -> str:
    """Mint a request-scoped correlation id. Deterministic within a process run
    (monotonic counter) so simulations stay reproducible."""
    return f"{prefix}{next(_counter):08d}"


@dataclass(frozen=True)
class Trace:
    """Threaded through every event so one request is reconstructable end-to-end."""
    correlation_id: str            # stable for the whole request, e.g. "R00000001"
    party: str                     # user | marketplace | seller
    stage: str                     # search | ad_source | bid | impress | click | cart | purchase | settle
    parent_id: str | None = None   # span chaining
