"""KnowledgeProvider served by the platform. v1 exposes brand_perception only
(issue #41 decision). Deterministic from the brand string so runs are reproducible;
a real reviews-backed KG/SQLite store can replace ``_derive`` later.
"""
from __future__ import annotations

import hashlib

from coms.infra import register


def _derive(brand: str) -> dict:
    if not brand:
        return {"trust": 0.5, "sentiment": 0.0}
    h = int(hashlib.sha256(brand.encode()).hexdigest(), 16)
    trust = 0.3 + (h % 1000) / 1000 * 0.6            # 0.3–0.9
    sentiment = ((h // 1000) % 1000) / 1000 * 2 - 1  # -1..1
    return {"trust": round(trust, 3), "sentiment": round(sentiment, 3)}


class BrandPerceptionProvider:
    """Backends: 'brand_perception' (derived). Cached per brand."""

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}

    def brand_perception(self, brand: str) -> dict:
        if brand not in self._cache:
            self._cache[brand] = _derive(brand)
        return self._cache[brand]


def _make(cfg: dict):
    return BrandPerceptionProvider()


register("knowledge", "brand_perception", _make)
