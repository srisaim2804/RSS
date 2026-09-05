"""Sample user personas with observable + hidden features and grounded queries."""
from __future__ import annotations

import numpy as np

from coms.contracts import UserPersona, ObservedFeatures, HiddenFeatures

_SEGMENTS = ("bargain", "premium", "brand_loyal", "impulsive", "general")


def _queries_from_catalog(products, rng, n: int) -> tuple[str, ...]:
    out = []
    for _ in range(n):
        p = products[int(rng.integers(len(products)))]
        toks = p.title.split()
        k = max(1, len(toks) - int(rng.integers(0, 2)))
        out.append(" ".join(toks[:k]))
    return tuple(dict.fromkeys(out))  # dedupe, keep order


def sample_users(n_users: int, products, seed: int = 0) -> list[UserPersona]:
    rng = np.random.default_rng(seed ^ 0x5EED)
    users = []
    for i in range(n_users):
        seg = str(rng.choice(_SEGMENTS))
        price_sens = {"bargain": 8.5, "premium": 2.5}.get(seg, float(rng.uniform(3, 7)))
        brand_loyal = 0.85 if seg == "brand_loyal" else float(rng.uniform(0.1, 0.6))
        impulse = 0.8 if seg == "impulsive" else float(rng.uniform(0.2, 0.6))
        obs = ObservedFeatures(
            age=int(rng.integers(18, 70)),
            device_type=str(rng.choice(("mobile", "desktop", "tablet"))),
            price_sensitivity=price_sens,
            ad_susceptibility=float(rng.uniform(1, 9)),
            review_dependency=float(rng.uniform(1, 9)),
            brand_loyalty=brand_loyal,
            domain_knowledge=str(rng.choice(("low", "moderate", "high"))))
        hid = HiddenFeatures(
            true_budget_ceiling=float(rng.uniform(50, 600)),
            impulse_threshold=impulse,
            social_proof_weight=float(rng.uniform(0.2, 0.9)),
            novelty_bias=float(rng.uniform(0.1, 0.8)),
            variety_seeking=float(rng.uniform(0.1, 0.9)))
        users.append(UserPersona(
            user_id=f"U{i:05d}", segment=seg, observed=obs, hidden=hid,
            queries=_queries_from_catalog(products, rng, int(rng.integers(2, 5)))))
    return users
