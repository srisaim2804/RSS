"""Four-repo system tests — exercise rss-coms + rss-usim + rss-mplc + rss-slrs together.

Skipped automatically if the party packages aren't installed (so `rss-coms` alone still
passes); run in full when all four are present.
"""
import pytest

pytest.importorskip("usim")
pytest.importorskip("mplc")
pytest.importorskip("slrs")

from coms.harness import SystemConfig, run_simulation  # noqa: E402
from coms.trace import CorrelatedEventLog  # noqa: E402


def test_full_simulation_produces_metrics_and_correlated_timeline():
    log = CorrelatedEventLog()
    cfg = SystemConfig()
    cfg.run = {"rounds": 3, "seeds": [0], "queries_per_round": 30}
    out = run_simulation(cfg, seed=0, event_log=log)

    sysm = out["system"]
    assert sysm["n_marketplaces"] == 1
    assert sysm["platform_revenue"] > 0
    assert sysm["total_purchases"] > 0
    assert sysm["total_welfare"] > 0

    # the known last request is reconstructable across all three parties
    tl = log.timeline(out["last_correlation_id"])
    assert tl, "correlated timeline empty"
    stages = [e.stage for e in tl]
    assert stages[0] == "search" and "settle" in stages
    assert {"user", "marketplace"} <= {e.party for e in tl}


def test_determinism_same_seed():
    a = run_simulation(SystemConfig(), seed=0)["system"]
    b = run_simulation(SystemConfig(), seed=0)["system"]
    assert a["platform_revenue"] == b["platform_revenue"]
    assert a["total_purchases"] == b["total_purchases"]


def test_two_party_mode_has_no_ad_revenue():
    cfg = SystemConfig()
    cfg.sellers = {"enabled": False}
    cfg.run = {"rounds": 2, "seeds": [0], "queries_per_round": 20}
    out = run_simulation(cfg, seed=0)
    assert out["system"]["platform_revenue"] == 0.0     # organic-only → no ad charges


def test_multi_marketplace_aggregates():
    cfg = SystemConfig()
    cfg.run = {"rounds": 2, "seeds": [0], "queries_per_round": 20}
    cfg.marketplaces = [
        {"id": "a", "plugin": "mplc", "ad_sourcing": "hosted", "ad_slots": 3, "organic_slots": 5},
        {"id": "b", "plugin": "mplc", "ad_sourcing": "hosted", "ad_slots": 2, "organic_slots": 6},
    ]
    out = run_simulation(cfg, seed=0)
    assert out["system"]["n_marketplaces"] == 2
    assert set(out["per_market"]) == {"a", "b"}


def test_rtb_topology_runs():
    cfg = SystemConfig()
    cfg.run = {"rounds": 2, "seeds": [0], "queries_per_round": 20}
    cfg.marketplaces = [{"id": "rtb", "plugin": "mplc", "ad_sourcing": "rtb",
                         "ad_slots": 3, "organic_slots": 5}]
    out = run_simulation(cfg, seed=0)
    assert out["system"]["n_marketplaces"] == 1
