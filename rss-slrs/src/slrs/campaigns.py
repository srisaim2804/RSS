"""Build campaign definitions + initial bid controls for a set of sellers."""
from __future__ import annotations

import numpy as np

from coms.contracts import CampaignSpec, KeywordBid, BidControls


def build_campaigns(sellers, product_map, seed: int = 0):
    """One campaign per seller over its products; keywords from product titles."""
    rng = np.random.default_rng(seed ^ 0xCA37)
    specs, controls = [], []
    for si, s in enumerate(sellers):
        prods = [product_map[p] for p in s.product_ids if p in product_map]
        if not prods:
            continue
        # keyword bids: one per distinct title token, priced off product value
        kw_bid: dict[str, float] = {}
        for p in prods:
            bid = round(0.3 + p.price * 0.004, 2)
            for tok in set(p.title.lower().split()):
                kw_bid[tok] = max(kw_bid.get(tok, 0.0), bid)
        cid = f"C{si:04d}"
        specs.append(CampaignSpec(
            campaign_id=cid, seller_id=s.seller_id,
            product_ids=tuple(p.product_id for p in prods),
            keyword_bids=tuple(KeywordBid(k, v) for k, v in kw_bid.items()),
            target_segments=("general",)))
        controls.append(BidControls(
            cid, bid_multiplier=1.0,
            daily_budget=float(round(rng.uniform(20, 80) * len(prods), 2)),
            pace_mode="even"))
    return specs, controls
