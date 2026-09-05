"""slrs contrib: opt-in group + the example aggressive fleet loads and bids higher."""
from importlib.metadata import entry_points

from coms.harness import synth_catalog
from coms.infra import registry


def test_contrib_is_optin_group():
    core = {ep.name: ep.value for ep in entry_points(group="rss.plugins")}
    contrib = {ep.name: ep.value for ep in entry_points(group="rss.contrib")}
    assert contrib.get("slrs", "").endswith("contrib._loader")
    assert core.get("slrs", "").endswith(".plugin")


def test_contrib_fleet_loads_and_bids_higher():
    registry.load_contrib()
    prods = synth_catalog(30, 6, seed=0)
    fleet = registry.make("seller_source", {
        "name": "contrib:aggressive", "products": prods, "n_sellers": 6, "seed": 0})
    specs, controls = fleet.initial_campaigns()
    assert specs and controls
    assert all(c.bid_multiplier == 1.5 for c in controls)   # aggressive opener
