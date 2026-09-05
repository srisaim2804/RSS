"""mplc contrib: opt-in group + the example knowledge backend loads and plugs into the
marketplace by config name."""
from importlib.metadata import entry_points

import numpy as np

from coms.contracts import UserPersona, UserAction
from coms.harness import synth_catalog
from coms.infra import registry
from mplc import Marketplace


class _Choice:
    def sample(self, user, page, knowledge, rng, position_decay=0.7):
        # probe knowledge so the test exercises the plugged-in backend
        self.seen_trust = knowledge.brand_perception(page.slots[0].brand)["trust"] if page.slots else None
        return [UserAction(s.position, s.slot_type, "seen", s.product_id,
                           s.campaign_id, s.seller_id, s.price, s.cpc) for s in page.slots]


def test_contrib_is_optin_group():
    core = {ep.name: ep.value for ep in entry_points(group="rss.plugins")}
    contrib = {ep.name: ep.value for ep in entry_points(group="rss.contrib")}
    assert contrib.get("mplc", "").endswith("contrib._loader")
    assert core.get("mplc", "").endswith(".plugin")


def test_contrib_knowledge_backend_loads():
    registry.load_contrib()
    k = registry.make("knowledge", {"name": "contrib:optimistic"})
    assert k.brand_perception("Acme") == {"trust": 0.9, "sentiment": 0.5}


def test_marketplace_uses_contrib_knowledge_by_name():
    prods = synth_catalog(20, 5, seed=0)
    choice = _Choice()
    mkt = Marketplace("mkt", prods, choice, ad_slots=0, organic_slots=4,
                      knowledge="contrib:optimistic")
    mkt.run_query(UserPersona("U1"), prods[0].title, np.random.default_rng(0), correlation_id="R1")
    assert choice.seen_trust == 0.9        # the contrib backend was used
