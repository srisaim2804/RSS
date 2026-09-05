"""RTB bidder — used only when a marketplace runs ad_sourcing='rtb'.

The ad lives on the seller side; the marketplace calls ``bid(request)`` per query and
we return creative + bid in real time (only observable user features are shared).
"""
from __future__ import annotations

from coms.contracts import BidRequest, BidResponse


class RTBBidder:
    def __init__(self, specs, controls_by_id, product_map) -> None:
        self._specs = specs
        self._controls = controls_by_id
        self._pmap = product_map

    def bid(self, request: BidRequest) -> list[BidResponse]:
        toks = set(request.query.lower().split())
        out = []
        for spec in self._specs:
            ctl = self._controls.get(spec.campaign_id)
            if ctl is None or ctl.status != "active":
                continue
            hit = [kb for kb in spec.keyword_bids if kb.keyword.lower() in toks]
            if not hit:
                continue
            product = next((self._pmap[p] for p in spec.product_ids if p in self._pmap), None)
            if product is None:
                continue
            bid = max(kb.bid_amount for kb in hit) * ctl.bid_multiplier
            out.append(BidResponse(spec.campaign_id, spec.seller_id, product.product_id, bid))
        out.sort(key=lambda r: -r.bid_amount)
        return out[: request.n_slots]
