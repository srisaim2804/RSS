"""Platform agent — optional per-round regulator adjustment (e.g. tighten quality
screening when ad load hurts welfare). Minimal for v1."""
from __future__ import annotations

from dataclasses import dataclass

from .marketplace import Marketplace


@dataclass
class PlatformAgent:
    marketplace: Marketplace
    target_min_quality: float = 0.0

    def step(self, round_idx: int, snapshot: dict) -> None:
        self.marketplace._reg.min_quality = self.target_min_quality
