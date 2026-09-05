"""Example contrib for rss-slrs: a seller-fleet variant.

Registers under the `seller_source` family with a `contrib:` name. Select it in config:
`[sellers] plugin = "contrib:aggressive"`.
"""
from dataclasses import replace

from coms.infra import register

from slrs.policy import SellerFleet


class AggressiveFleet(SellerFleet):
    """Same fleet, but opens every campaign at a higher bid multiplier."""

    def initial_campaigns(self):
        specs, controls = super().initial_campaigns()
        controls = [replace(c, bid_multiplier=1.5) for c in controls]
        self._controls = {c.campaign_id: c for c in controls}
        return specs, controls


def _make(cfg):
    return AggressiveFleet(cfg["products"], cfg.get("n_sellers", 12),
                           cfg.get("seed", 0), cfg.get("marketplace_id", "mkt"))


register("seller_source", "contrib:aggressive", _make)
