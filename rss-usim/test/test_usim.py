import numpy as np

from coms.contracts import SlotObservation, ObservationPage
from coms.harness import synth_catalog
from usim import sample_users, IndependentFunnelChoiceModel


class _Knowledge:
    def __init__(self, trust=0.7, sentiment=0.3):
        self.trust, self.sentiment = trust, sentiment

    def brand_perception(self, brand):
        return {"trust": self.trust, "sentiment": self.sentiment}


def _page(prods, n=5):
    return ObservationPage("wireless mouse", tuple(
        SlotObservation(i, "ad" if i == 0 else "organic", p.product_id, p.title,
                        p.price, p.rating, p.brand, relevance=0.8 - 0.1 * i,
                        is_sponsored=(i == 0), campaign_id="c1" if i == 0 else None,
                        seller_id="s1", cpc=0.5 if i == 0 else 0.0)
        for i, p in enumerate(prods[:n])))


def test_sampling_deterministic():
    prods = synth_catalog(30, 6, seed=0)
    a = sample_users(15, prods, seed=7)
    b = sample_users(15, prods, seed=7)
    assert [u.user_id for u in a] == [u.user_id for u in b]
    assert a[0].observed.price_sensitivity == b[0].observed.price_sensitivity
    assert len(a) == 15 and all(u.queries for u in a)


def test_choice_returns_action_per_slot():
    prods = synth_catalog(30, 6, seed=0)
    users = sample_users(3, prods, seed=1)
    page = _page(prods)
    acts = IndependentFunnelChoiceModel().sample(users[0], page, _Knowledge(), np.random.default_rng(0))
    assert len(acts) == len(page.slots)
    assert all(a.action in ("not_seen", "seen", "clicked", "cart", "purchased") for a in acts)


def test_funnel_is_monotonic():
    prods = synth_catalog(30, 6, seed=0)
    users = sample_users(3, prods, seed=1)
    # purchased implies price within budget (enforced by the model)
    acts = IndependentFunnelChoiceModel().sample(users[0], _page(prods), _Knowledge(), np.random.default_rng(2))
    for a in acts:
        if a.action == "purchased":
            assert a.price <= users[0].hidden.true_budget_ceiling


def test_brand_trust_shifts_clicks():
    """Higher brand trust/sentiment should not reduce aggregate clicks (probe matters)."""
    prods = synth_catalog(40, 6, seed=0)
    users = sample_users(40, prods, seed=3)
    page = _page(prods)
    cm = IndependentFunnelChoiceModel()

    def clicks(know, seed):
        rng = np.random.default_rng(seed)
        n = 0
        for u in users:
            for a in cm.sample(u, page, know, rng):
                n += a.action in ("clicked", "cart", "purchased")
        return n

    low = clicks(_Knowledge(trust=0.2, sentiment=-0.4), 5)
    high = clicks(_Knowledge(trust=0.95, sentiment=0.6), 5)
    assert high >= low
