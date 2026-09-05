"""The top-level system config that wires the world (system.toml)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SystemConfig:
    run: dict = field(default_factory=lambda: {"rounds": 5, "seeds": [0], "queries_per_round": 40})
    users: dict = field(default_factory=lambda: {"plugin": "usim", "n_users": 50})
    sellers: dict = field(default_factory=lambda: {"enabled": True, "plugin": "slrs", "n_sellers": 12})
    catalog: dict = field(default_factory=lambda: {"n_products": 60, "n_brands": 8})
    marketplaces: list = field(default_factory=lambda: [
        {"id": "mkt", "plugin": "mplc", "transport": "inproc",
         "ad_sourcing": "hosted", "knowledge": "brand_perception",
         "ad_slots": 3, "organic_slots": 5, "mechanism": "gsp"}])
    health: dict = field(default_factory=dict)

    @property
    def two_party(self) -> bool:
        return not self.sellers.get("enabled", True)


def load_system(path: str | Path) -> SystemConfig:
    raw = tomllib.loads(Path(path).read_text())
    base = SystemConfig()
    for k in ("run", "users", "sellers", "catalog", "health"):
        if k in raw:
            base.__dict__[k] = {**base.__dict__[k], **raw[k]}
    if "marketplaces" in raw:
        base.marketplaces = raw["marketplaces"]
    return base
