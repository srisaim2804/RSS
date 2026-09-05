"""The simulation harness. Resolves parties from the registry (entry points) and
drives the multi-round loop. No static import of any party package.

Supports: single/multi marketplace, two-party (no sellers) mode, hosted + RTB ad
sourcing, and the correlated event log threaded through every request.
"""
from __future__ import annotations

import numpy as np

from coms.contracts import new_correlation_id
from coms.infra import registry
from coms.trace import CorrelatedEventLog
from .catalog import synth_catalog
from .system_config import SystemConfig


def _pick_query(user, rng, products) -> str:
    if user.queries:
        return user.queries[int(rng.integers(len(user.queries)))]
    p = products[int(rng.integers(len(products)))]
    toks = p.title.split()
    return " ".join(toks[: max(1, len(toks) - 1)])


def run_simulation(cfg: SystemConfig, seed: int = 0,
                   event_log: CorrelatedEventLog | None = None) -> dict:
    registry.load_plugins()
    log = event_log if event_log is not None else CorrelatedEventLog()
    rng = np.random.default_rng(seed)

    products = synth_catalog(cfg.catalog.get("n_products", 60),
                             cfg.catalog.get("n_brands", 8), seed=seed)

    users = registry.make("user_source", {
        "name": cfg.users.get("plugin", "usim"),
        "n_users": cfg.users.get("n_users", 50),
        "seed": seed, "products": products})
    choice_model = registry.make("choice_model", {
        "name": cfg.users.get("choice_model", "independent_funnel")})

    rounds = cfg.run.get("rounds", 5)
    qpr = cfg.run.get("queries_per_round", 40)

    per_market: dict[str, dict] = {}
    last_cid = None

    for mcfg in cfg.marketplaces:
        two_party = cfg.two_party
        ad_sourcing = "hosted" if two_party else mcfg.get("ad_sourcing", "hosted")

        fleet = None
        if not two_party:
            fleet = registry.make("seller_source", {
                "name": cfg.sellers.get("plugin", "slrs"),
                "n_sellers": cfg.sellers.get("n_sellers", 12),
                "marketplace_id": mcfg["id"], "seed": seed, "products": products})

        mkt = registry.make("marketplace", {
            "name": mcfg.get("plugin", "mplc"),
            "id": mcfg["id"], "products": products, "choice_model": choice_model,
            "event_log": log, "ad_sourcing": ad_sourcing,
            "knowledge": mcfg.get("knowledge", "brand_perception"),
            "ad_slots": 0 if two_party else mcfg.get("ad_slots", 3),
            "organic_slots": mcfg.get("organic_slots", 5),
            "mechanism": mcfg.get("mechanism", "gsp"),
            "position_decay": mcfg.get("position_decay", 0.7),
            "bidder": fleet.bidder() if (fleet and ad_sourcing == "rtb") else None,
            "search_index": mcfg.get("search_index", "word_overlap"),
            "search_index_cfg": mcfg.get("search_index_cfg"),
            "personalize": mcfg.get("personalize", "off"),
            "personalize_cfg": mcfg.get("personalize_cfg")})

        if fleet is not None and ad_sourcing == "hosted":
            specs, controls = fleet.initial_campaigns()
            for s in specs:
                mkt.upsert_campaign(s)
            for c in controls:
                mkt.set_controls(c)

        for r in range(rounds):
            mkt.reset_day()
            if fleet is not None and ad_sourcing == "hosted":
                for c in fleet.step(r, mkt.snapshot()):
                    mkt.set_controls(c)
            for _ in range(qpr):
                user = users[int(rng.integers(len(users)))]
                query = _pick_query(user, rng, products)
                last_cid = new_correlation_id()
                mkt.run_query(user, query, rng, correlation_id=last_cid)
            if fleet is not None:
                fleet.observe(mkt.snapshot())

        per_market[mcfg["id"]] = mkt.snapshot()

    system = _aggregate(per_market)
    return {"seed": seed, "per_market": per_market, "system": system,
            "event_log": log, "last_correlation_id": last_cid}


def _aggregate(per_market: dict[str, dict]) -> dict:
    keys = set().union(*[m.keys() for m in per_market.values()]) if per_market else set()
    out = {}
    for k in keys:
        vals = [m[k] for m in per_market.values() if isinstance(m.get(k), (int, float))]
        if vals:
            out[k] = sum(vals)
    out["n_marketplaces"] = len(per_market)
    return out
