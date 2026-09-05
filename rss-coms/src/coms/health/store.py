"""Persistent per-round welfare snapshots (SQLite) for the dashboards."""
from __future__ import annotations

import sqlite3


class RoundUtilityStore:
    def __init__(self, path: str | None = None) -> None:
        self._db = sqlite3.connect(path or ":memory:")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS round_platform ("
            "round INTEGER, marketplace TEXT, revenue REAL, welfare REAL, impressions INTEGER)")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS round_metrics (round INTEGER, key TEXT, value REAL)")
        self._db.commit()

    def write_round(self, round_idx: int, metrics: dict, marketplace: str = "mkt") -> None:
        self._db.execute(
            "INSERT INTO round_platform VALUES (?,?,?,?,?)",
            (round_idx, marketplace, metrics.get("platform_revenue", 0.0),
             metrics.get("total_welfare", 0.0), metrics.get("impressions", 0)))
        self._db.executemany(
            "INSERT INTO round_metrics VALUES (?,?,?)",
            [(round_idx, k, float(v)) for k, v in metrics.items() if isinstance(v, (int, float))])
        self._db.commit()

    def rounds(self) -> list[dict]:
        cur = self._db.execute("SELECT round, revenue, welfare, impressions FROM round_platform ORDER BY round")
        return [{"round": r, "revenue": rev, "welfare": w, "impressions": i}
                for r, rev, w, i in cur.fetchall()]

    def close(self) -> None:
        self._db.close()
