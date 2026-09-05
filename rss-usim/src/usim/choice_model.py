"""Choice model — consumes the platform's observable projection and probes knowledge.

Never imports marketplace or seller internals: it reads only ``ObservationPage`` +
``KnowledgeProvider.brand_perception``. This is the decoupled replacement for the old
``user ↔ marketplace`` import cycle.
"""
from __future__ import annotations

import numpy as np

from coms.contracts import ObservationPage, UserAction, UserPersona
from coms.infra import register


def _clip(x: float) -> float:
    return float(min(0.98, max(0.0, x)))


class IndependentFunnelChoiceModel:
    """Per-slot independent funnel: seen → clicked → cart → purchased."""

    def sample(self, user: UserPersona, page: ObservationPage, knowledge,
               rng: np.random.Generator, position_decay: float = 0.7) -> list[UserAction]:
        obs, hid = user.observed, user.hidden
        out: list[UserAction] = []
        for slot in page.slots:
            bp = knowledge.brand_perception(slot.brand) if knowledge else {"trust": 0.5, "sentiment": 0.0}
            trust = float(bp.get("trust", 0.5))
            sentiment = float(bp.get("sentiment", 0.0))

            p_seen = position_decay ** slot.position
            # click: relevance-driven, boosted by ad susceptibility (ads), rating, brand trust
            base = 0.04 + 0.5 * slot.relevance
            if slot.is_sponsored:
                base *= 1.0 + 0.06 * obs.ad_susceptibility
            base *= 1.0 + 0.05 * (slot.rating - 3.0)
            base *= 1.0 + 0.02 * obs.review_dependency * (trust - 0.5) * 2
            base *= 1.0 + obs.brand_loyalty * sentiment * 0.3
            p_click = _clip(base)
            # cart: affordability + impulse + novelty
            afford = 1.0 - min(1.0, slot.price / max(1.0, hid.true_budget_ceiling))
            p_cart = _clip(0.35 * afford + 0.3 * hid.impulse_threshold + 0.2 * trust)
            # purchase: price sensitivity vs budget ceiling
            price_penalty = (obs.price_sensitivity / 10.0) * min(1.0, slot.price / max(1.0, hid.true_budget_ceiling))
            p_purchase = _clip(0.7 * afford + 0.3 * hid.social_proof_weight * trust - 0.4 * price_penalty)

            action = "not_seen"
            if rng.random() < p_seen:
                action = "seen"
                if rng.random() < p_click:
                    action = "clicked"
                    if rng.random() < p_cart:
                        action = "cart"
                        if slot.price <= hid.true_budget_ceiling and rng.random() < p_purchase:
                            action = "purchased"
            out.append(UserAction(
                slot=slot.position, slot_type=slot.slot_type, action=action,
                product_id=slot.product_id, campaign_id=slot.campaign_id,
                seller_id=slot.seller_id, price=slot.price, cpc=slot.cpc,
                p_seen=p_seen, p_click=p_click, p_cart=p_cart, p_purchase=p_purchase))
        return out


def _make(cfg: dict):
    return IndependentFunnelChoiceModel()


register("choice_model", "independent_funnel", _make)
