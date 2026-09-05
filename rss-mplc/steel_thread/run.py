#!/usr/bin/env python
"""Steel thread for rss-mplc (runs against a mock choice model — no party needed).

    python steel_thread/run.py --path search|auction|knowledge|full
"""
from __future__ import annotations

import argparse
import numpy as np

from coms.contracts import UserPersona, CampaignSpec, KeywordBid, BidControls
from coms.harness import synth_catalog
from mplc import Marketplace, run_auction, BrandPerceptionProvider
from mplc.search import MockSearchIndex


class _Choice:
    """Clicks slot 0, buys if affordable — deterministic, for wiring checks."""
    def sample(self, user, page, knowledge, rng, position_decay=0.7):
        from coms.contracts import UserAction
        out = []
        for s in page.slots:
            act = "seen"
            if s.position == 0:
                act = "purchased" if s.price <= user.hidden.true_budget_ceiling else "clicked"
            out.append(UserAction(s.position, s.slot_type, act, s.product_id,
                                  s.campaign_id, s.seller_id, s.price, s.cpc))
        return out


def _campaigns(products):
    specs, controls = [], []
    for i, p in enumerate(products[:6]):
        kw = p.title.split()[0]
        cid = f"c{i}"
        specs.append(CampaignSpec(cid, f"s{i}", (p.product_id,), (KeywordBid(kw, 1.0 + i * 0.2),)))
        controls.append(BidControls(cid, bid_multiplier=1.0, daily_budget=1000.0))
    return specs, controls


def path_search():
    prods = synth_catalog(40, 6, seed=0)
    idx = MockSearchIndex(); idx.index(prods)
    q = prods[0].title
    hits = idx.search(q, 5)
    print(f"[search] '{q}' → {len(hits)} hits, top={hits[0]['product'].product_id}")
    assert hits and hits[0]["relevance"] > 0
    print("[search] OK")


def path_auction():
    prods = synth_catalog(40, 6, seed=0)
    q = prods[0].title.split()[0]
    cands = [{"campaign_id": f"c{i}", "seller_id": f"s{i}", "product": p, "bid": 1.0 + i}
             for i, p in enumerate(prods[:5])]
    winners = run_auction(q, cands, 3, np.random.default_rng(0), "gsp")
    print(f"[auction] {len(winners)} winners, cpcs={[w['cpc'] for w in winners]}")
    assert all(w["cpc"] <= w["bid"] for w in winners)
    print("[auction] OK")


def path_knowledge():
    kp = BrandPerceptionProvider()
    a, b = kp.brand_perception("Acme"), kp.brand_perception("Acme")
    assert a == b and 0 <= a["trust"] <= 1 and -1 <= a["sentiment"] <= 1
    print(f"[knowledge] Acme → {a}")
    print("[knowledge] OK")


def path_full():
    prods = synth_catalog(40, 6, seed=0)
    mkt = Marketplace("mkt", prods, _Choice(), ad_slots=3, organic_slots=4)
    for s in _campaigns(prods)[0]:
        mkt.upsert_campaign(s)
    for c in _campaigns(prods)[1]:
        mkt.set_controls(c)
    rng = np.random.default_rng(0)
    u = UserPersona("U1", queries=(prods[0].title,))
    qr = mkt.run_query(u, prods[0].title.split()[0], rng, correlation_id="R1")
    tl = mkt._log.timeline("R1")
    print(f"[full] actions={len(qr.actions)} charged={qr.total_charged:.3f} "
          f"purchased={qr.n_purchased} events={[e.stage for e in tl][:6]}")
    assert any(e.stage == "search" for e in tl) and any(e.stage == "settle" for e in tl)
    print("[full] OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="full", choices=["search", "auction", "knowledge", "full"])
    {"search": path_search, "auction": path_auction,
     "knowledge": path_knowledge, "full": path_full}[ap.parse_args().path]()


if __name__ == "__main__":
    main()
