"""The marketplace — implements coms MarketplaceService.

Per query: organic search + sponsored auction → observable page → injected choice model
→ settlement → correlated events + utility/health accounting. Owns the private
``ProductScore`` (never exposed) and serves the ``KnowledgeProvider``.
"""
from __future__ import annotations

import numpy as np

from coms.contracts import (
    ObservationPage, SlotObservation, QueryResult, SettleResult, ActionEvent,
    BidRequest, new_correlation_id,
)
from coms.health import UtilityLedger, MetricsTracker, extract_metrics
from coms.infra import SimClock, make as _make_component
from coms.trace import CorrelatedEventLog

from .search import MockSearchIndex
from .personalize import NoPersonalizer
from .ads import HostedCampaignRegistry
from .auction import run_auction
from .regulator import Regulator
from .knowledge import BrandPerceptionProvider


class Marketplace:
    def __init__(self, id: str, products, choice_model, *,
                 event_log: CorrelatedEventLog | None = None,
                 ad_sourcing: str = "hosted", knowledge: str = "brand_perception",
                 ad_slots: int = 3, organic_slots: int = 5,
                 mechanism: str = "gsp", position_decay: float = 0.7,
                 bidder=None, search_index: str = "word_overlap",
                 search_index_cfg: dict | None = None,
                 personalize: str = "off",
                 personalize_cfg: dict | None = None) -> None:
        self.id = id
        self._pmap = {p.product_id: p for p in products}
        self._choice = choice_model
        self._log = event_log if event_log is not None else CorrelatedEventLog()
        self._ad_sourcing = ad_sourcing
        self._ad_slots = ad_slots
        self._organic_slots = organic_slots
        self._mechanism = mechanism
        self._decay = position_decay
        self._bidder = bidder
        self._clock = SimClock()
        # organic ranker is config-selectable (builtin "word_overlap" / "semantic",
        # or a contrib: backend); falls back to the builtin if the name isn't
        # registered — same pattern as the knowledge backend below.
        try:
            self._search = _make_component(
                "search_index", {"name": search_index, **(search_index_cfg or {})})
        except KeyError:
            self._search = MockSearchIndex()
        self._search.index(products)
        self._registry = HostedCampaignRegistry(self._pmap)
        # knowledge backend is config-selectable (builtin "brand_perception" or a
        # contrib: provider); falls back to the builtin if the name isn't registered.
        try:
            self._knowledge = _make_component("knowledge", {"name": knowledge})
        except KeyError:
            self._knowledge = BrandPerceptionProvider()
        # per-user organic re-rank (builtin "off" / "rules"); "off" is identity and
        # keeps the pool fetch at exactly organic_slots → byte-identical behaviour.
        try:
            self._personalizer = _make_component(
                "personalizer", {"name": personalize, **(personalize_cfg or {})})
        except KeyError:
            self._personalizer = NoPersonalizer()
        self._personalize_on = not isinstance(self._personalizer, NoPersonalizer)
        self._reg = Regulator()
        self.ledger = UtilityLedger(id)
        self.tracker = MetricsTracker()

    # ── CampaignRegistry passthrough (hosted model) ──────────────────────────
    def upsert_campaign(self, spec) -> None:
        self._registry.upsert_campaign(spec)

    def set_controls(self, controls) -> None:
        self._registry.set_controls(controls)

    def reset_day(self) -> None:
        self._registry.reset_day()

    # ── knowledge probe served to the choice model ───────────────────────────
    def brand_perception(self, brand: str) -> dict:
        return self._knowledge.brand_perception(brand)

    # ── the seam ─────────────────────────────────────────────────────────────
    def run_query(self, user, query: str, rng: np.random.Generator, *,
                  correlation_id: str | None = None) -> QueryResult:
        cid = correlation_id or new_correlation_id()
        events: list[ActionEvent] = []

        def emit(party, stage, **kw):
            events.append(ActionEvent(correlation_id=cid, tick=self._clock.tick(),
                                      party=party, stage=stage, user_id=user.user_id,
                                      query=query, **kw))

        emit("user", "search")

        # sponsored auction
        winners = []
        if self._ad_slots > 0:
            if self._ad_sourcing == "rtb" and self._bidder is not None:
                req = BidRequest(cid, query, user.segment, user.observed.device_type, self._ad_slots)
                cands = []
                for r in self._bidder.bid(req):
                    p = self._pmap.get(r.product_id)
                    if p is not None:
                        cands.append({"campaign_id": r.campaign_id, "seller_id": r.seller_id,
                                      "product": p, "bid": r.bid_amount})
            else:
                cands = self._registry.candidates(query)
            winners = run_auction(query, cands, self._ad_slots, rng,
                                  self._mechanism, self._reg.min_quality)
            for w in winners:
                emit("seller", "ad_source", product_id=w["product"].product_id,
                     campaign_id=w["campaign_id"], seller_id=w["seller_id"], slot_type="ad")

        # observable page: ads first, then organic (deduped)
        slots, pos, shown = [], 0, set()
        for w in winners:
            p = w["product"]
            shown.add(p.product_id)
            slots.append(SlotObservation(pos, "ad", p.product_id, p.title, p.price,
                                         p.rating, p.brand, relevance=w["relevance"],
                                         is_sponsored=True, campaign_id=w["campaign_id"],
                                         seller_id=w["seller_id"], cpc=w["cpc"]))
            pos += 1
        n_org = self._organic_slots
        pool = max(n_org * 4, n_org) if self._personalize_on else n_org
        hits = self._search.search(query, pool)
        if self._personalize_on:
            hits = self._personalizer.reorder(user, hits, self.brand_perception)
        filled = 0
        for h in hits:
            if filled >= n_org:
                break
            p = h["product"]
            if p.product_id in shown:
                continue
            slots.append(SlotObservation(pos, "organic", p.product_id, p.title, p.price,
                                         p.rating, p.brand, relevance=float(h["relevance"]),
                                         seller_id=p.seller_id or None))
            pos += 1
            filled += 1
        page = ObservationPage(query, tuple(slots))

        actions = self._choice.sample(user, page, self, rng, self._decay)

        settle, total_charged, n_purch = [], 0.0, 0
        self.ledger.record_session()
        for a in actions:
            seen = a.action in ("seen", "clicked", "cart", "purchased")
            clicked = a.action in ("clicked", "cart", "purchased")
            charged = revenue = cogs = surplus = value = 0.0
            if clicked and a.slot_type == "ad" and a.campaign_id:
                charged = a.cpc
                self._registry.charge(a.campaign_id, charged)
                total_charged += charged
            if a.action == "purchased":
                p = self._pmap[a.product_id]
                revenue, cogs = p.price, p.cogs_unit
                surplus = max(0.0, p.price * (0.6 + 0.08 * p.rating) - p.price)
                value = surplus + (revenue - cogs)
                n_purch += 1
            self.ledger.record(user_id=user.user_id, segment=user.segment,
                               seller_id=a.seller_id, charged=charged, revenue=revenue,
                               cogs=cogs, user_surplus=surplus, value_created=value,
                               impression=seen)
            self.tracker.record_action(a, a.action)
            if seen:
                emit("user", a.action, product_id=a.product_id, campaign_id=a.campaign_id,
                     seller_id=a.seller_id, slot=a.slot, slot_type=a.slot_type,
                     action=a.action, cpc=charged, price=revenue)
            settle.append(SettleResult(charged=charged, revenue=revenue, cogs=cogs,
                                       clicked=clicked, purchased=(a.action == "purchased")))

        emit("marketplace", "settle", cpc=total_charged)
        self._log.write_many(events)
        return QueryResult(query, user.user_id, cid, tuple(actions), tuple(settle),
                           n_purch, total_charged)

    def run_queries_batch(self, items, rng):
        return [self.run_query(u, q, rng, correlation_id=c) for (u, q, c) in items]

    def snapshot(self) -> dict:
        m = extract_metrics(self.ledger, self.tracker)
        imps = self.ledger.platform.impressions
        m["ad_load"] = (self._ad_slots / max(1, self._ad_slots + self._organic_slots))
        m["marketplace_id"] = self.id
        return m
