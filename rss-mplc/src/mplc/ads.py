"""Hosted-campaign model: the ad lives on the platform (issue #41 default).

Sellers ``upsert_campaign`` a definition once, then push ``BidControls`` each round;
the marketplace sources ads from this registry at auction time. Inverted keyword index
gives O(candidates) matching.
"""
from __future__ import annotations

from coms.contracts import CampaignSpec, BidControls
from .scoring import overlap


class HostedCampaignRegistry:
    """Satisfies coms CampaignRegistry."""

    def __init__(self, product_map: dict) -> None:
        self._products = product_map                 # product_id -> Product
        self._specs: dict[str, CampaignSpec] = {}
        self._controls: dict[str, BidControls] = {}
        self._kw: dict[str, set[str]] = {}
        self._spent: dict[str, float] = {}

    def upsert_campaign(self, spec: CampaignSpec) -> None:
        self._specs[spec.campaign_id] = spec
        self._controls.setdefault(spec.campaign_id, BidControls(spec.campaign_id))
        self._spent.setdefault(spec.campaign_id, 0.0)
        for kb in spec.keyword_bids:
            for tok in kb.keyword.lower().split():
                self._kw.setdefault(tok, set()).add(spec.campaign_id)

    def set_controls(self, controls: BidControls) -> None:
        self._controls[controls.campaign_id] = controls

    def reset_day(self) -> None:
        self._spent = {cid: 0.0 for cid in self._spent}

    def charge(self, campaign_id: str, amount: float) -> None:
        self._spent[campaign_id] = self._spent.get(campaign_id, 0.0) + amount

    def campaign_ids(self) -> list[str]:
        return list(self._specs)

    def candidates(self, query: str) -> list[dict]:
        toks = set(query.lower().split())
        cids: set[str] = set()
        for t in toks:
            cids |= self._kw.get(t, set())
        out = []
        for cid in sorted(cids):
            ctl = self._controls.get(cid)
            spec = self._specs[cid]
            if ctl is None or ctl.status != "active":
                continue
            if self._spent.get(cid, 0.0) >= ctl.daily_budget:
                continue
            # best matching product in the campaign
            prods = [self._products[p] for p in spec.product_ids if p in self._products]
            if not prods:
                continue
            product = max(prods, key=lambda p: overlap(query, p.title))
            max_bid = max(kb.bid_amount for kb in spec.keyword_bids)
            out.append({"campaign_id": cid, "seller_id": spec.seller_id,
                        "product": product, "bid": max_bid * ctl.bid_multiplier})
        return out
