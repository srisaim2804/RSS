"""Sample sellers from a product catalog (grouped by brand)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Seller:
    seller_id: str
    name: str
    product_ids: list[str] = field(default_factory=list)
    cogs_ratio: float = 0.5
    value_per_conversion_ratio: float = 0.3


def sample_sellers(products, n_sellers: int, seed: int = 0) -> list[Seller]:
    rng = np.random.default_rng(seed ^ 0x5E11E5)
    # group products by brand, then fold brands into n_sellers buckets
    by_brand: dict[str, list] = {}
    for p in products:
        by_brand.setdefault(p.brand or "misc", []).append(p)
    brands = sorted(by_brand)
    n = max(1, min(n_sellers, len(brands)))
    sellers = [Seller(f"S{i:04d}", f"seller-{brands[i % len(brands)]}") for i in range(n)]
    for i, b in enumerate(brands):
        s = sellers[i % n]
        s.product_ids.extend(p.product_id for p in by_brand[b])
    for s in sellers:
        s.cogs_ratio = float(rng.uniform(0.35, 0.65))
        s.value_per_conversion_ratio = float(rng.uniform(0.2, 0.4))
    return [s for s in sellers if s.product_ids]
