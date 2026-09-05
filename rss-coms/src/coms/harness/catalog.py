"""Neutral synthetic product catalog (commons data).

Independent of sellers so that two-party (search-only) mode still has a catalog to
retrieve over. When sellers are enabled, rss-slrs builds campaigns over these products.
"""
from __future__ import annotations

import numpy as np

from coms.contracts import Product

_WORDS = ["wireless", "bluetooth", "gaming", "ergonomic", "portable", "premium",
          "compact", "rugged", "smart", "noise", "cancelling", "mechanical",
          "headphones", "mouse", "keyboard", "speaker", "charger", "webcam",
          "monitor", "laptop", "stand", "hub", "cable", "adapter"]
_BRANDS = ["Acme", "Nimbus", "Volt", "Orbit", "Peak", "Lumen", "Forge", "Zephyr",
           "Kilo", "Delta", "Pico", "Terra"]


def synth_catalog(n_products: int = 60, n_brands: int = 8, seed: int = 0) -> list[Product]:
    rng = np.random.default_rng(seed)
    brands = _BRANDS[:max(1, min(n_brands, len(_BRANDS)))]
    out = []
    for i in range(n_products):
        n_tokens = int(rng.integers(2, 5))
        title = " ".join(rng.choice(_WORDS, size=n_tokens, replace=False))
        price = float(round(rng.uniform(10, 400), 2))
        out.append(Product(
            product_id=f"P{i:05d}", title=title, price=price,
            rating=float(round(rng.uniform(3.0, 5.0), 2)),
            brand=str(rng.choice(brands)),
            cogs_unit=round(price * float(rng.uniform(0.35, 0.65)), 2)))
    return out
