"""Entry-point module (rss.plugins → slrs). Importing registers slrs components."""
from __future__ import annotations

from coms.infra import register

from .policy import SellerFleet


def _seller_source(cfg: dict):
    return SellerFleet(
        products=cfg["products"], n_sellers=cfg.get("n_sellers", 12),
        seed=cfg.get("seed", 0), marketplace_id=cfg.get("marketplace_id", "mkt"),
        strategy=cfg.get("strategy", "adaptive_roas"))


register("seller_source", "slrs", _seller_source)
