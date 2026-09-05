"""Sponsored-ad auction: quality-weighted allocation + GSP / first-price pricing."""
from __future__ import annotations

import numpy as np

from .scoring import score_product


def run_auction(query, candidates: list[dict], n_slots: int, rng: np.random.Generator,
                mechanism: str = "gsp", min_quality: float = 0.0) -> list[dict]:
    """Return up to n_slots winners as dicts with product, campaign_id, seller_id,
    quality, cpc. Candidates: [{campaign_id, seller_id, product, bid}]."""
    scored = []
    for c in candidates:
        ps = score_product(query, c["product"], rng)
        if ps.quality < min_quality:
            continue
        scored.append({**c, "quality": ps.quality, "relevance": ps.relevance,
                       "rank_score": c["bid"] * ps.quality})
    scored.sort(key=lambda x: (-x["rank_score"], x["campaign_id"]))
    winners = scored[:n_slots]
    for i, w in enumerate(winners):
        if mechanism == "first_price":
            cpc = w["bid"]
        else:  # gsp: pay just enough to keep your slot vs the next-ranked
            if i + 1 < len(scored):
                nxt = scored[i + 1]
                cpc = nxt["rank_score"] / max(1e-6, w["quality"])
            else:
                cpc = w["bid"] * 0.5   # reserve-ish floor for the last slot
            cpc = min(cpc, w["bid"])
        w["cpc"] = round(float(cpc), 4)
    return winners
