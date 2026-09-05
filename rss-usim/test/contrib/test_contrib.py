"""usim contrib: opt-in group + the example choice-model variant loads and runs."""
from importlib.metadata import entry_points

import numpy as np

from coms.contracts import SlotObservation, ObservationPage
from coms.harness import synth_catalog
from coms.infra import registry
from usim import sample_users


class _K:
    def brand_perception(self, brand):
        return {"trust": 0.7, "sentiment": 0.2}


def test_contrib_is_optin_group():
    # contrib is a separate group whose entry points the loader (not the builtin plugin)
    core = {ep.name: ep.value for ep in entry_points(group="rss.plugins")}
    contrib = {ep.name: ep.value for ep in entry_points(group="rss.contrib")}
    assert contrib.get("usim", "").endswith("contrib._loader")
    assert core.get("usim", "").endswith(".plugin")   # core loads the builtin, not contrib


def test_contrib_choice_model_loads_and_runs():
    registry.load_contrib()
    cm = registry.make("choice_model", {"name": "contrib:noisy_funnel"})
    prods = synth_catalog(20, 5, seed=0)
    users = sample_users(3, prods, seed=0)
    page = ObservationPage("q", tuple(
        SlotObservation(i, "organic", p.product_id, p.title, p.price, p.rating, p.brand, 0.6)
        for i, p in enumerate(prods[:4])))
    acts = cm.sample(users[0], page, _K(), np.random.default_rng(0))
    assert len(acts) == len(page.slots)
