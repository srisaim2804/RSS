"""Correlated event log — the single sink all three parties write to.

Every event carries a ``correlation_id`` (+ optional ``parent_id``) so one request is
reconstructable end to end. Example: a user search ``R00000001`` arriving at the
platform, passed to sellers, ads sourced and impressed, then clicked — all rows share
``correlation_id='R00000001'`` and ``timeline()`` returns them in tick order.

Backends: in-memory (default, fast, for tests/steel-thread) or SQLite (persistent,
dashboard-friendly). Satisfies the ``EventStore`` interface.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from coms.contracts import ActionEvent

_COLS = ("correlation_id", "tick", "party", "stage", "user_id", "query",
         "product_id", "campaign_id", "seller_id", "slot", "slot_type",
         "action", "cpc", "price", "parent_id", "extra")


class CorrelatedEventLog:
    """Cross-party event log. ``path=None`` → in-memory list; else SQLite file."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path
        self._mem: list[ActionEvent] = []
        self._db: sqlite3.Connection | None = None
        if path:
            self._db = sqlite3.connect(path)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "correlation_id TEXT, tick INTEGER, party TEXT, stage TEXT,"
                "user_id TEXT, query TEXT, product_id TEXT, campaign_id TEXT,"
                "seller_id TEXT, slot INTEGER, slot_type TEXT, action TEXT,"
                "cpc REAL, price REAL, parent_id TEXT, extra TEXT)")
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS ix_corr ON events(correlation_id)")
            self._db.commit()

    # ── EventStore interface ──────────────────────────────────────────────────
    def write(self, event: ActionEvent) -> None:
        if self._db is None:
            self._mem.append(event)
            return
        d = asdict(event)
        d["extra"] = json.dumps(d["extra"])
        self._db.execute(
            f"INSERT INTO events ({','.join(_COLS)}) VALUES ({','.join('?' * len(_COLS))})",
            tuple(d[c] for c in _COLS))

    def write_many(self, events: list[ActionEvent]) -> None:
        for e in events:
            self.write(e)
        if self._db is not None:
            self._db.commit()

    def close(self) -> None:
        if self._db is not None:
            self._db.commit()
            self._db.close()
            self._db = None

    # ── Correlation query ─────────────────────────────────────────────────────
    def timeline(self, correlation_id: str) -> list[ActionEvent]:
        """The full, tick-ordered event chain for one request."""
        if self._db is None:
            rows = [e for e in self._mem if e.correlation_id == correlation_id]
            return sorted(rows, key=lambda e: e.tick)
        cur = self._db.execute(
            f"SELECT {','.join(_COLS)} FROM events WHERE correlation_id=? ORDER BY tick",
            (correlation_id,))
        out = []
        for row in cur.fetchall():
            d = dict(zip(_COLS, row))
            d["extra"] = json.loads(d["extra"]) if d["extra"] else {}
            out.append(ActionEvent(**d))
        return out

    def correlation_ids(self) -> list[str]:
        if self._db is None:
            return sorted({e.correlation_id for e in self._mem})
        cur = self._db.execute("SELECT DISTINCT correlation_id FROM events")
        return sorted(r[0] for r in cur.fetchall())

    def all(self) -> list[ActionEvent]:
        if self._db is None:
            return list(self._mem)
        return [e for cid in self.correlation_ids() for e in self.timeline(cid)]


def timeline(log: CorrelatedEventLog, correlation_id: str) -> list[ActionEvent]:
    """Free-function form: coms.trace.timeline(log, 'R00000001')."""
    return log.timeline(correlation_id)
