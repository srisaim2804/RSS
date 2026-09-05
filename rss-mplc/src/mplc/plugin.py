"""Entry-point module (rss.plugins → mplc). Importing registers mplc components."""
from __future__ import annotations

from coms.infra import register

from . import knowledge  # noqa: F401  (registers knowledge/brand_perception)
from . import search  # noqa: F401  (registers search_index/word_overlap + bm25 + semantic + behavioral)
from . import personalize  # noqa: F401  (registers personalizer/off + rules)
from .marketplace import Marketplace


def _marketplace(cfg: dict):
    return Marketplace(
        id=cfg.get("id", "mkt"), products=cfg["products"],
        choice_model=cfg["choice_model"], event_log=cfg.get("event_log"),
        ad_sourcing=cfg.get("ad_sourcing", "hosted"),
        knowledge=cfg.get("knowledge", "brand_perception"),
        ad_slots=cfg.get("ad_slots", 3), organic_slots=cfg.get("organic_slots", 5),
        mechanism=cfg.get("mechanism", "gsp"),
        position_decay=cfg.get("position_decay", 0.7), bidder=cfg.get("bidder"),
        search_index=cfg.get("search_index", "word_overlap"),
        search_index_cfg=cfg.get("search_index_cfg"),
        personalize=cfg.get("personalize", "off"),
        personalize_cfg=cfg.get("personalize_cfg"))


register("marketplace", "mplc", _marketplace)
