"""Per-user re-rank of the organic result list.

The ``SearchIndex`` seam has no access to the user, so personalization runs in the
marketplace: :meth:`Marketplace.run_query` over-fetches an organic candidate pool
from the ranker, then a ``personalizer`` reorders it before the slots are built.

The reorder is a *perturbation* of the ranker's order, not a replacement: each
candidate keeps a base score from its rank in the pool and gains
``weight · bonus(user, product)``, where the bonus is a small signed number built
from the user's observable features (price sensitivity / segment, brand loyalty ×
brand trust, review dependency × rating). With the default weight a candidate can
move a few positions, not from last to first — relevance still dominates.

Registered under the ``personalizer`` plugin family: ``off`` (identity) and
``rules`` (the heuristic below).
"""
from __future__ import annotations

from coms.infra import register

_NEUTRAL_BP = {"trust": 0.5, "sentiment": 0.0}


class NoPersonalizer:
    """Identity — the default. Returns the ranker's order untouched."""

    def reorder(self, user, hits, brand_perception=None):
        return hits


class RulePersonalizer:
    """Heuristic per-user re-rank (see module docstring)."""

    def __init__(self, weight: float = 0.5, price_ref: float = 200.0) -> None:
        self._w = float(weight)
        self._price_ref = max(1.0, float(price_ref))

    def _bonus(self, user, p, brand_perception) -> float:
        obs = user.observed
        expensiveness = min(1.0, p.price / self._price_ref)          # 0..1
        if user.segment == "premium":
            price_term = 0.8 * expensiveness                          # premium likes pricier
        else:
            ps = obs.price_sensitivity / 10.0                         # 0..1
            price_term = ps * (0.5 - expensiveness) * 2.0             # sensitive → cheaper up
        bp = (brand_perception(p.brand) if brand_perception else _NEUTRAL_BP) or _NEUTRAL_BP
        brand_term = obs.brand_loyalty * (float(bp.get("trust", 0.5)) - 0.5) * 2.0
        rating_term = (obs.review_dependency / 10.0) * (p.rating - 3.0) / 2.0
        b = 0.5 * price_term + 0.3 * brand_term + 0.2 * rating_term
        return max(-1.0, min(1.0, b))

    def reorder(self, user, hits, brand_perception=None):
        n = len(hits)
        if n <= 1:
            return list(hits)
        scored = []
        for i, h in enumerate(hits):
            base = 1.0 - i / n                                        # ranker order, 1 = best
            scored.append((base + self._w * self._bonus(user, h["product"], brand_perception),
                           i, h))
        scored.sort(key=lambda x: (-x[0], x[1]))                      # tie-break: original rank
        return [h for _, _, h in scored]


def _mk_off(cfg: dict):
    return NoPersonalizer()


def _mk_rules(cfg: dict):
    return RulePersonalizer(weight=cfg.get("weight", 0.5),
                            price_ref=cfg.get("price_ref", 200.0))


register("personalizer", "off", _mk_off)
register("personalizer", "rules", _mk_rules)
