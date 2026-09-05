"""Seller fleet — all of this plugin's sellers/campaigns and their bidding policy.

Satisfies coms ``SellerPolicy``: ``initial_campaigns`` / ``step`` / ``observe`` / ``bidder``.
The bidding logic sits here (seller side); the campaign object itself lives on the
platform (hosted model). ``step`` emits updated ``BidControls`` each round.
"""
from __future__ import annotations

from dataclasses import replace

from .sellers import sample_sellers
from .campaigns import build_campaigns
from .bidder import RTBBidder


class SellerFleet:
    def __init__(self, products, n_sellers: int, seed: int = 0,
                 marketplace_id: str = "mkt", strategy: str = "adaptive_roas") -> None:
        self.marketplace_id = marketplace_id
        self.strategy = strategy
        self._pmap = {p.product_id: p for p in products}
        self.sellers = sample_sellers(products, n_sellers, seed)
        self._specs, controls = build_campaigns(self.sellers, self._pmap, seed)
        self._controls = {c.campaign_id: c for c in controls}

    # ── SellerPolicy interface ────────────────────────────────────────────────
    def initial_campaigns(self):
        return list(self._specs), list(self._controls.values())

    def step(self, round_idx: int, snapshot: dict) -> list:
        """Adaptive: nudge bids toward a ROAS target using the platform snapshot."""
        roas = float(snapshot.get("seller_roas_mean", 0.0))
        if self.strategy == "deterministic" or roas == 0.0:
            factor = 1.0
        elif roas > 2.0:
            factor = 1.05
        elif roas < 1.0:
            factor = 0.95
        else:
            factor = 1.0
        for cid, c in self._controls.items():
            mult = min(2.0, max(0.5, c.bid_multiplier * factor))
            self._controls[cid] = replace(c, bid_multiplier=round(mult, 4))
        return list(self._controls.values())

    def observe(self, snapshot: dict) -> None:
        self._last = snapshot

    def bidder(self):
        return RTBBidder(self._specs, self._controls, self._pmap)
