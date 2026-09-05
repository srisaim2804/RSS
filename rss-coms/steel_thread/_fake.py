"""A minimal in-repo MarketplaceService used by the transport steel thread / tests,
so rss-coms can verify transport parity without any party package installed."""
from __future__ import annotations

import numpy as np

from coms.contracts import QueryResult, UserAction, SettleResult


class FakeMarketplace:
    id = "mkt"

    def __init__(self, id: str = "mkt") -> None:
        self.id = id
        self._rev = 0.0

    def run_query(self, user, query, rng: np.random.Generator, *, correlation_id=None):
        # deterministic function of the rng stream only → transport parity is testable
        cpc = float(rng.uniform(0.1, 1.0))
        clicked = bool(rng.random() < 0.5)
        charged = cpc if clicked else 0.0
        self._rev += charged
        act = UserAction(slot=0, slot_type="ad", action="clicked" if clicked else "seen",
                         product_id="P1", campaign_id="c1", seller_id="s1",
                         price=10.0, cpc=cpc)
        return QueryResult(query=query, user_id=user.user_id,
                           correlation_id=correlation_id or "R0",
                           actions=(act,), settle=(SettleResult(charged=charged, clicked=clicked),),
                           n_purchased=0, total_charged=charged)

    def run_queries_batch(self, items, rng):
        return [self.run_query(u, q, rng, correlation_id=c) for (u, q, c) in items]

    def reset_day(self):
        pass

    def upsert_campaign(self, spec):
        pass

    def set_controls(self, controls):
        pass

    def snapshot(self) -> dict:
        return {"platform_revenue": self._rev}
