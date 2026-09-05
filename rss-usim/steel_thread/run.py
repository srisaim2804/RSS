#!/usr/bin/env python
"""Steel thread for rss-usim (runs against mock counterparts — no other party needed).

    python steel_thread/run.py --path sampling
    python steel_thread/run.py --path choice
"""
from __future__ import annotations

import argparse
import numpy as np

from coms.contracts import Product, SlotObservation, ObservationPage
from coms.harness import synth_catalog
from usim import sample_users, IndependentFunnelChoiceModel


class _Knowledge:
    def brand_perception(self, brand):
        return {"trust": 0.7, "sentiment": 0.3}


def path_sampling():
    prods = synth_catalog(30, 6, seed=0)
    users = sample_users(20, prods, seed=0)
    segs = {u.segment for u in users}
    print(f"[sampling] {len(users)} users, segments={sorted(segs)}, "
          f"e.g. {users[0].user_id} queries={users[0].queries[:2]}")
    assert len(users) == 20 and users[0].queries
    print("[sampling] OK")


def path_choice():
    prods = synth_catalog(30, 6, seed=0)
    users = sample_users(5, prods, seed=1)
    page = ObservationPage("wireless mouse", tuple(
        SlotObservation(i, "ad" if i == 0 else "organic", p.product_id, p.title,
                        p.price, p.rating, p.brand, relevance=0.8 - 0.1 * i,
                        is_sponsored=(i == 0), campaign_id="c1" if i == 0 else None,
                        seller_id=p.seller_id or "s1", cpc=0.5 if i == 0 else 0.0)
        for i, p in enumerate(prods[:5])))
    cm = IndependentFunnelChoiceModel()
    acts = cm.sample(users[0], page, _Knowledge(), np.random.default_rng(0))
    stages = ["not_seen", "seen", "clicked", "cart", "purchased"]
    for a in acts:
        assert a.action in stages
        # funnel monotonicity: a later stage implies its probabilities are defined
        if a.action == "purchased":
            assert a.price <= users[0].hidden.true_budget_ceiling
    print(f"[choice] {len(acts)} actions: {[a.action for a in acts]}")
    print("[choice] OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="sampling", choices=["sampling", "choice"])
    {"sampling": path_sampling, "choice": path_choice}[ap.parse_args().path]()


if __name__ == "__main__":
    main()
