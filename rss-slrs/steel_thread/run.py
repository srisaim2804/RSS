#!/usr/bin/env python
"""Steel thread for rss-slrs (no other party needed).

    python steel_thread/run.py --path sample|campaign|bid
"""
from __future__ import annotations

import argparse

from coms.contracts import BidRequest
from coms.harness import synth_catalog
from slrs import sample_sellers, SellerFleet


def path_sample():
    prods = synth_catalog(60, 8, seed=0)
    sellers = sample_sellers(prods, 10, seed=0)
    print(f"[sample] {len(sellers)} sellers, e.g. {sellers[0].seller_id} "
          f"with {len(sellers[0].product_ids)} products")
    assert sellers and all(s.product_ids for s in sellers)
    print("[sample] OK")


def path_campaign():
    prods = synth_catalog(60, 8, seed=0)
    fleet = SellerFleet(prods, 10, seed=0)
    specs, controls = fleet.initial_campaigns()
    print(f"[campaign] {len(specs)} campaigns; c0 keywords={len(specs[0].keyword_bids)} "
          f"budget={controls[0].daily_budget}")
    assert specs and controls and specs[0].keyword_bids
    # step reacts to a high-ROAS snapshot → bids rise
    before = controls[0].bid_multiplier
    updated = fleet.step(1, {"seller_roas_mean": 3.0})
    print(f"[campaign] bid_multiplier {before} → {updated[0].bid_multiplier} (roas=3.0)")
    assert updated[0].bid_multiplier > before
    print("[campaign] OK")


def path_bid():
    prods = synth_catalog(60, 8, seed=0)
    fleet = SellerFleet(prods, 10, seed=0)
    bidder = fleet.bidder()
    q = prods[0].title
    resp = bidder.bid(BidRequest("R1", q, "general", "mobile", 3))
    print(f"[bid] query '{q}' → {len(resp)} bids, top={resp[0] if resp else None}")
    assert resp, "expected at least one RTB bid for a catalog query"
    print("[bid] OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="sample", choices=["sample", "campaign", "bid"])
    {"sample": path_sample, "campaign": path_campaign, "bid": path_bid}[ap.parse_args().path]()


if __name__ == "__main__":
    main()
