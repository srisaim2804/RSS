"""Behavioral signal learned from a prior round's actions log.

The brief is explicit that the log is confounded: "Position and propensity bias
the log, so actions are not ground-truth relevance." So instead of a raw
click-rate, this builds an inverse-propensity-weighted (IPS) estimate — each row
contributes 1/propensity, not 1, undoing the exploration policy's own sampling
bias before treating the result as a relevance-ish signal. Rows with an
unusably small propensity are clipped rather than allowed to blow up the
estimate.

Two things are learned:
  * a global per-item IPS click rate (folds in query/session ambiguity, since a
    single round rarely gives enough rows per (query, item) pair to estimate that
    finer-grained)
  * per-user, the set of brands they've clicked, to stand in for `brand_loyalty`
    now that we have a non-guessed way to apply it (the raw feature's sign/scale
    is undocumented, per ranker.py's fit_adjustment docstring).
"""
from __future__ import annotations

import numpy as np
import pyarrow.parquet as pq

_CLICK_ACTIONS = {"click", "cart", "purchase"}
_MIN_PROPENSITY = 0.02


def load_actions(path) -> dict:
    table = pq.read_table(str(path))
    return {c: table.column(c).to_pylist() for c in table.column_names}


class Behavioral:
    def __init__(self, bundle, actions: dict, item_weight: float = 0.025,
                 brand_weight: float = 0.015) -> None:
        self.item_weight = item_weight
        self.brand_weight = brand_weight
        self._item_index = bundle._item_index_by_id
        self._brand_by_item = bundle.item_brand

        n = len(bundle.item_ids)
        num = np.zeros(n)
        den = np.zeros(n)
        clicked_brands: dict[str, set[str]] = {}

        item_ids = actions.get("item_id", [])
        user_ids = actions.get("user_id", [])
        actions_col = actions.get("action", [])
        propensity_col = actions.get("propensity") or [1.0] * len(item_ids)

        for item_id, user_id, action, prop in zip(item_ids, user_ids, actions_col, propensity_col):
            idx = self._item_index.get(item_id)
            if idx is None:
                continue
            prop = max(float(prop) if prop else 1.0, _MIN_PROPENSITY)
            w = 1.0 / prop
            clicked = action in _CLICK_ACTIONS
            num[idx] += w if clicked else 0.0
            den[idx] += w
            if clicked:
                clicked_brands.setdefault(user_id, set()).add(str(self._brand_by_item[idx]))

        global_ctr = float(num.sum() / den.sum()) if den.sum() > 0 else 0.0
        # shrink low-exposure items toward the global mean instead of trusting a
        # 1-impression 100% or 0% estimate
        shrink_k = 5.0
        self.item_ctr = (num + shrink_k * global_ctr) / np.maximum(den + shrink_k, 1e-9)
        self.global_ctr = global_ctr
        self.clicked_brands = clicked_brands
        # base term depends on neither query nor user — compute once, not per call
        self._base_adj = item_weight * np.tanh((self.item_ctr - global_ctr) * 10.0)
        self._adj_cache: dict[str, np.ndarray] = {}

    def adjustment(self, bundle, query_id: str, user_id: str) -> np.ndarray:
        """Depends only on user_id, not query_id — cached per user (at most 400
        of them) rather than recomputed per (query, user) pair (up to 14.4k),
        since the brand-membership mask is an O(n_items) scan."""
        cached = self._adj_cache.get(user_id)
        if cached is not None:
            return cached
        adj = self._base_adj
        brands = self.clicked_brands.get(user_id)
        if brands:
            loyalty = max(0.0, float(bundle.user_by_id[user_id]["brand_loyalty"]))
            if loyalty > 0.0:
                mask = np.isin(self._brand_by_item, list(brands))
                adj = adj + self.brand_weight * min(1.0, loyalty) * mask
        self._adj_cache[user_id] = adj
        return adj
