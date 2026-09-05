from coms.contracts import BidRequest, CampaignSpec, BidControls
from coms.harness import synth_catalog
from slrs import sample_sellers, build_campaigns, SellerFleet


def test_sample_sellers_deterministic():
    prods = synth_catalog(60, 8, seed=0)
    a = sample_sellers(prods, 10, seed=1)
    b = sample_sellers(prods, 10, seed=1)
    assert [s.seller_id for s in a] == [s.seller_id for s in b]
    assert all(s.product_ids for s in a)


def test_build_campaigns_shapes():
    prods = synth_catalog(40, 6, seed=0)
    sellers = sample_sellers(prods, 6, seed=0)
    pmap = {p.product_id: p for p in prods}
    specs, controls = build_campaigns(sellers, pmap, seed=0)
    assert len(specs) == len(controls)
    assert all(isinstance(s, CampaignSpec) and s.keyword_bids for s in specs)
    assert all(isinstance(c, BidControls) and c.daily_budget > 0 for c in controls)


def test_fleet_initial_and_adaptive_step():
    prods = synth_catalog(60, 8, seed=0)
    fleet = SellerFleet(prods, 10, seed=0)
    specs, controls = fleet.initial_campaigns()
    assert specs and controls
    base = controls[0].bid_multiplier
    up = fleet.step(1, {"seller_roas_mean": 3.0})[0].bid_multiplier
    down = fleet.step(2, {"seller_roas_mean": 0.5})[0].bid_multiplier
    assert up > base and down < up            # rises on high ROAS, falls on low
    assert 0.5 <= down <= 2.0                  # clamped


def test_rtb_bidder_matches_query():
    prods = synth_catalog(60, 8, seed=0)
    fleet = SellerFleet(prods, 10, seed=0)
    resp = fleet.bidder().bid(BidRequest("R1", prods[0].title, "general", "mobile", 3))
    assert resp and resp[0].bid_amount > 0
    assert resp == sorted(resp, key=lambda r: -r.bid_amount)   # ranked by bid
