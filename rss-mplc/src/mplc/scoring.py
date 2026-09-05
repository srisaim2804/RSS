"""Product scoring. ``ProductScore`` (ctr/cvr/relevance latents) is PRIVATE to rss-mplc —
it never leaves this repo. The platform reveals only ``relevance`` on SlotObservation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ProductScore:
    ctr: float
    cvr: float
    relevance: float

    @property
    def quality(self) -> float:
        # allocation weight — bounded (0,1], dominated by relevance
        return max(1e-3, self.relevance)


def _clip(x, lo=0.0, hi=0.99):
    return float(min(hi, max(lo, x)))


def overlap(query: str, title: str) -> float:
    q = set(query.lower().split())
    if not q:
        return 0.0
    t = set(title.lower().split())
    return len(q & t) / len(q)


def score_product(query: str, product, rng: np.random.Generator) -> ProductScore:
    ov = overlap(query, product.title)
    relevance = _clip(0.20 + 0.60 * ov + rng.normal(0, 0.05))
    ctr = _clip(0.03 + 0.02 * product.rating / 5 + rng.normal(0, 0.01))
    cvr = _clip(0.12 - 0.08 * min(product.price / 400, 1.0) + rng.normal(0, 0.015))
    return ProductScore(ctr=ctr, cvr=cvr, relevance=relevance)
