import numpy as np

from coms.contracts import UserPersona, CampaignSpec, KeywordBid, BidControls, UserAction
from coms.harness import synth_catalog
from mplc import Marketplace, run_auction, BrandPerceptionProvider
from coms.contracts import Product, ObservedFeatures
from mplc.search import (
    MockSearchIndex, SemanticSearchIndex, BM25SearchIndex, ClickAwareSearchIndex,
    BlendedSearchIndex)
from mplc.personalize import NoPersonalizer, RulePersonalizer
from mplc.scoring import score_product, ProductScore, overlap


class _Choice:
    def sample(self, user, page, knowledge, rng, position_decay=0.7):
        out = []
        for s in page.slots:
            act = "purchased" if (s.position == 0 and s.price <= user.hidden.true_budget_ceiling) else "seen"
            out.append(UserAction(s.position, s.slot_type, act, s.product_id,
                                  s.campaign_id, s.seller_id, s.price, s.cpc))
        return out


def _mkt(ad_slots=3):
    prods = synth_catalog(40, 6, seed=0)
    mkt = Marketplace("mkt", prods, _Choice(), ad_slots=ad_slots, organic_slots=4)
    for i, p in enumerate(prods[:6]):
        cid = f"c{i}"
        mkt.upsert_campaign(CampaignSpec(cid, f"s{i}", (p.product_id,),
                                         (KeywordBid(p.title.split()[0], 1.0 + i),)))
        mkt.set_controls(BidControls(cid, daily_budget=1000.0))
    return prods, mkt


def test_search_overlap():
    prods = synth_catalog(30, 6, seed=0)
    idx = MockSearchIndex(); idx.index(prods)
    hits = idx.search(prods[0].title, 5)
    assert hits and hits[0]["relevance"] > 0


def test_semantic_index_same_candidates_and_pure_overlap_relevance():
    prods = synth_catalog(60, 8, seed=0)
    q = " ".join(prods[3].title.split()[:2])
    lex = MockSearchIndex(); lex.index(prods)
    sem = SemanticSearchIndex(); sem.index(prods)
    lex_hits = lex.search(q, 50)
    sem_hits = sem.search(q, 50)
    # semantic only reorders — never adds or drops a candidate
    assert {h["product"].product_id for h in lex_hits} == {h["product"].product_id for h in sem_hits}
    # relevance reported to the choice model stays pure token overlap (not the cosine)
    for h in sem_hits:
        assert h["relevance"] == overlap(q, h["product"].title)


def test_semantic_index_sem_weight_zero_matches_word_overlap_order():
    prods = synth_catalog(60, 8, seed=0)
    q = " ".join(prods[7].title.split()[:2])
    lex = MockSearchIndex(); lex.index(prods)
    sem = SemanticSearchIndex(sem_weight=0.0); sem.index(prods)
    assert ([h["product"].product_id for h in lex.search(q, 20)]
            == [h["product"].product_id for h in sem.search(q, 20)])


def test_marketplace_wires_semantic_index_end_to_end():
    prods = synth_catalog(40, 6, seed=0)
    mkt = Marketplace("mkt", prods, _Choice(), ad_slots=0, organic_slots=5,
                      search_index="semantic",
                      search_index_cfg={"sem_weight": 0.6, "n_components": 12})
    assert type(mkt._search).__name__ == "SemanticSearchIndex"
    u = UserPersona("U1")
    qr = mkt.run_query(u, prods[0].title, np.random.default_rng(0), correlation_id="RS")
    assert qr.actions and all(a.slot_type == "organic" for a in qr.actions)


def test_bm25_same_candidates_and_pure_overlap_relevance():
    prods = synth_catalog(60, 8, seed=0)
    q = " ".join(prods[3].title.split()[:2])
    lex = MockSearchIndex(); lex.index(prods)
    bm = BM25SearchIndex(); bm.index(prods)
    assert ({h["product"].product_id for h in lex.search(q, 50)}
            == {h["product"].product_id for h in bm.search(q, 50)})
    for h in bm.search(q, 50):
        assert h["relevance"] == overlap(q, h["product"].title)


def test_bm25_promotes_rarer_term_match_over_word_overlap_tiebreak():
    # P0 matches the common term "common", P1 the rare term "rare"; both overlap
    # 0.5 and every title is 2 tokens, so word-overlap tie-breaks on product_id
    # (P0 < P1 < Z*  ->  P0 first). BM25 gives "rare" (df=1) a far higher idf
    # than "common" (df=11), so P1 should win.
    prods = [Product("P0", "common alpha", 10.0), Product("P1", "rare beta", 10.0)]
    prods += [Product(f"Z{i}", "common gamma", 10.0) for i in range(10)]
    lex = MockSearchIndex(); lex.index(prods)
    bm = BM25SearchIndex(); bm.index(prods)
    assert lex.search("rare common", 5)[0]["product"].product_id == "P0"
    assert bm.search("rare common", 5)[0]["product"].product_id == "P1"


def test_marketplace_wires_bm25_index_end_to_end():
    prods = synth_catalog(40, 6, seed=0)
    mkt = Marketplace("mkt", prods, _Choice(), ad_slots=0, organic_slots=5,
                      search_index="bm25", search_index_cfg={"k1": 1.2, "b": 0.5})
    assert type(mkt._search).__name__ == "BM25SearchIndex"
    qr = mkt.run_query(UserPersona("U1"), prods[0].title,
                       np.random.default_rng(0), correlation_id="RB")
    assert qr.actions and all(a.slot_type == "organic" for a in qr.actions)


def test_blended_overlap_only_matches_word_overlap():
    prods = synth_catalog(60, 8, seed=0)
    q = " ".join(prods[4].title.split()[:2])
    lex = MockSearchIndex(); lex.index(prods)
    bl = BlendedSearchIndex(w_overlap=1.0, w_semantic=0.0, w_ctr=0.0); bl.index(prods)
    assert ([h["product"].product_id for h in lex.search(q, 20)]
            == [h["product"].product_id for h in bl.search(q, 20)])
    for h in bl.search(q, 20):
        assert h["relevance"] == overlap(q, h["product"].title)


def test_blended_ctr_term_promotes_high_ctr_item():
    prods = [Product("P0", "wireless mouse", 20.0), Product("P1", "wireless mouse", 25.0)]
    stats = {"global": 0.3, "item": {"P0": 0.1, "P1": 0.95}, "query_item": {}}
    bl = BlendedSearchIndex(w_overlap=1.0, w_ctr=4.0, stats=stats); bl.index(prods)
    assert bl.search("wireless mouse", 2)[0]["product"].product_id == "P1"


def test_blended_matches_behavioral_special_case():
    prods = synth_catalog(60, 8, seed=0)
    q = " ".join(prods[6].title.split()[:2])
    stats = {"global": 0.5,
             "item": {p.product_id: (0.2 + 0.6 * (int(p.product_id[-2:]) % 5) / 4)
                      for p in prods},
             "query_item": {}}
    beh = ClickAwareSearchIndex(ctr_weight=0.5, stats=stats); beh.index(prods)
    bl = BlendedSearchIndex(w_overlap=0.5, w_ctr=0.5, stats=stats); bl.index(prods)
    assert ([h["product"].product_id for h in beh.search(q, 20)]
            == [h["product"].product_id for h in bl.search(q, 20)])


def test_marketplace_wires_blended_index_end_to_end():
    prods = synth_catalog(40, 6, seed=0)
    stats = {"global": 0.5, "item": {p.product_id: 0.5 for p in prods}, "query_item": {}}
    mkt = Marketplace("m", prods, _Choice(), ad_slots=0, organic_slots=5,
                      search_index="blended",
                      search_index_cfg={"w_overlap": 1.0, "w_semantic": 0.3,
                                        "w_ctr": 0.6, "stats": stats})
    assert type(mkt._search).__name__ == "BlendedSearchIndex"
    qr = mkt.run_query(UserPersona("U1"), prods[0].title,
                       np.random.default_rng(0), correlation_id="RBL")
    assert qr.actions and all(a.slot_type == "organic" for a in qr.actions)


def test_semantic_cosine_map_in_range():
    prods = synth_catalog(40, 6, seed=0)
    sem = SemanticSearchIndex(); sem.index(prods)
    cos = sem.cosine(prods[0].title)
    assert set(cos) == {p.product_id for p in prods}
    assert all(0.0 <= v <= 1.0 for v in cos.values())


def _catalog_for_ctr():
    return [Product("P0", "wireless mouse", 20.0), Product("P1", "wireless mouse", 25.0),
            Product("P2", "wireless keyboard", 30.0)]


def test_behavioral_same_candidates_and_pure_overlap_relevance():
    prods = synth_catalog(60, 8, seed=0)
    q = " ".join(prods[3].title.split()[:2])
    stats = {"global": 0.5, "item": {p.product_id: 0.4 for p in prods}, "query_item": {}}
    lex = MockSearchIndex(); lex.index(prods)
    beh = ClickAwareSearchIndex(ctr_weight=0.6, stats=stats); beh.index(prods)
    assert ({h["product"].product_id for h in lex.search(q, 50)}
            == {h["product"].product_id for h in beh.search(q, 50)})
    for h in beh.search(q, 50):
        assert h["relevance"] == overlap(q, h["product"].title)


def test_behavioral_no_stats_keeps_word_overlap_order():
    prods = synth_catalog(60, 8, seed=0)
    q = " ".join(prods[7].title.split()[:2])
    lex = MockSearchIndex(); lex.index(prods)
    beh = ClickAwareSearchIndex(ctr_weight=0.5, stats=None); beh.index(prods)
    # every ctr_signal == global == 0.0 → blended is a monotonic scaling of overlap
    assert ([h["product"].product_id for h in lex.search(q, 20)]
            == [h["product"].product_id for h in beh.search(q, 20)])


def test_behavioral_promotes_high_ctr_item_over_overlap_tiebreak():
    prods = _catalog_for_ctr()
    stats = {"global": 0.3, "item": {"P0": 0.2, "P1": 0.9}, "query_item": {}}
    lex = MockSearchIndex(); lex.index(prods)
    beh = ClickAwareSearchIndex(ctr_weight=0.8, stats=stats); beh.index(prods)
    # P0, P1 tie on overlap(=1.0) → word-overlap orders P0 then P1
    assert [h["product"].product_id for h in lex.search("wireless mouse", 3)][:2] == ["P0", "P1"]
    # behavioural flips them: P1 has the far higher stored CTR
    assert beh.search("wireless mouse", 3)[0]["product"].product_id == "P1"


def test_behavioral_relevance_not_inflated_by_ctr():
    prods = _catalog_for_ctr()
    stats = {"global": 0.5, "item": {"P0": 1.0}, "query_item": {}}
    beh = ClickAwareSearchIndex(ctr_weight=0.9, stats=stats); beh.index(prods)
    hit = next(h for h in beh.search("wireless mouse", 3) if h["product"].product_id == "P0")
    assert hit["relevance"] == overlap("wireless mouse", "wireless mouse") == 1.0


def test_marketplace_wires_behavioral_index_end_to_end():
    prods = synth_catalog(40, 6, seed=0)
    stats = {"global": 0.5, "item": {p.product_id: 0.5 for p in prods}, "query_item": {}}
    mkt = Marketplace("mkt", prods, _Choice(), ad_slots=0, organic_slots=5,
                      search_index="behavioral",
                      search_index_cfg={"stats": stats, "ctr_weight": 0.4})
    assert type(mkt._search).__name__ == "ClickAwareSearchIndex"
    qr = mkt.run_query(UserPersona("U1"), prods[0].title,
                       np.random.default_rng(0), correlation_id="RH")
    assert qr.actions and all(a.slot_type == "organic" for a in qr.actions)


def _hits(*specs):
    # specs: (product_id, price[, rating[, brand]])
    out = []
    for s in specs:
        pid, price = s[0], s[1]
        rating = s[2] if len(s) > 2 else 4.0
        brand = s[3] if len(s) > 3 else "Acme"
        out.append({"product": Product(pid, "x", price, rating, brand), "relevance": 1.0})
    return out


_NEUTRAL_BP = lambda _b: {"trust": 0.5, "sentiment": 0.0}


def test_personalizer_off_is_identity():
    hits = _hits(("P0", 100.0), ("P1", 50.0), ("P2", 200.0))
    u = UserPersona("U", segment="bargain")
    assert NoPersonalizer().reorder(u, hits, _NEUTRAL_BP) == hits


def test_rule_personalizer_bargain_user_pulls_cheapest_up():
    hits = _hits(("EXP", 380.0), ("MID", 150.0), ("CHEAP", 20.0))   # ranker order
    u = UserPersona("U", segment="bargain",
                    observed=ObservedFeatures(price_sensitivity=9.0))
    out = RulePersonalizer(weight=100.0).reorder(u, hits, _NEUTRAL_BP)
    assert out[0]["product"].product_id == "CHEAP"


def test_rule_personalizer_premium_user_pulls_priciest_up():
    hits = _hits(("CHEAP", 20.0), ("MID", 150.0), ("EXP", 380.0))
    u = UserPersona("U", segment="premium",
                    observed=ObservedFeatures(price_sensitivity=2.5))
    out = RulePersonalizer(weight=100.0).reorder(u, hits, _NEUTRAL_BP)
    assert out[0]["product"].product_id == "EXP"


def test_rule_personalizer_default_weight_only_perturbs_order():
    # weight 0.5: a mild bonus can't lift the last candidate past the first
    hits = _hits(("TOP", 300.0), ("A", 300.0), ("B", 300.0), ("LAST", 10.0))
    u = UserPersona("U", segment="bargain",
                    observed=ObservedFeatures(price_sensitivity=9.0))
    out = RulePersonalizer(weight=0.5).reorder(u, hits, _NEUTRAL_BP)
    assert out[0]["product"].product_id == "TOP"          # relevance still dominates
    assert out[-1]["product"].product_id != "LAST"        # but the cheap one moved up


def test_marketplace_personalize_off_matches_plain_slot_order():
    prods = synth_catalog(50, 6, seed=0)
    q = prods[2].title
    base = Marketplace("m", prods, _Choice(), ad_slots=0, organic_slots=5)
    off = Marketplace("m", prods, _Choice(), ad_slots=0, organic_slots=5,
                      personalize="off")
    r1 = base.run_query(UserPersona("U1"), q, np.random.default_rng(0), correlation_id="A")
    r2 = off.run_query(UserPersona("U1"), q, np.random.default_rng(0), correlation_id="B")
    assert ([a.product_id for a in r1.actions] == [a.product_id for a in r2.actions])


def test_marketplace_wires_personalizer_end_to_end():
    prods = synth_catalog(50, 6, seed=0)
    mkt = Marketplace("m", prods, _Choice(), ad_slots=0, organic_slots=5,
                      personalize="rules", personalize_cfg={"weight": 0.8})
    assert type(mkt._personalizer).__name__ == "RulePersonalizer"
    u = UserPersona("U1", segment="bargain",
                    observed=ObservedFeatures(price_sensitivity=9.0))
    qr = mkt.run_query(u, prods[2].title, np.random.default_rng(0), correlation_id="RP")
    org = [a for a in qr.actions if a.slot_type == "organic"]
    assert 0 < len(org) <= 5


def test_gsp_price_below_bid_and_ordered():
    prods = synth_catalog(20, 4, seed=0)
    q = prods[0].title.split()[0]
    cands = [{"campaign_id": f"c{i}", "seller_id": f"s{i}", "product": p, "bid": 1.0 + i}
             for i, p in enumerate(prods[:5])]
    w = run_auction(q, cands, 3, np.random.default_rng(0), "gsp")
    assert len(w) <= 3
    assert all(x["cpc"] <= x["bid"] for x in w)


def test_scoring_is_private_type():
    prods = synth_catalog(5, 2, seed=0)
    ps = score_product("wireless", prods[0], np.random.default_rng(0))
    assert isinstance(ps, ProductScore) and 0 <= ps.relevance <= 1


def test_brand_perception_deterministic_in_range():
    kp = BrandPerceptionProvider()
    a, b = kp.brand_perception("Volt"), kp.brand_perception("Volt")
    assert a == b and 0 <= a["trust"] <= 1 and -1 <= a["sentiment"] <= 1


def test_run_query_emits_correlated_chain_and_no_score_leak():
    prods, mkt = _mkt()
    u = UserPersona("U1", queries=(prods[0].title,))
    qr = mkt.run_query(u, prods[0].title.split()[0], np.random.default_rng(0), correlation_id="R1")
    assert qr.correlation_id == "R1"
    tl = mkt._log.timeline("R1")
    stages = [e.stage for e in tl]
    assert "search" in stages and "settle" in stages
    # ProductScore latents must NOT appear on the observable slots
    # (SlotObservation has no ctr/cvr fields)
    from coms.contracts import SlotObservation
    assert not any(f in SlotObservation.__dataclass_fields__ for f in ("ctr", "cvr"))


def test_two_party_no_ads():
    prods = synth_catalog(30, 6, seed=0)
    mkt = Marketplace("mkt", prods, _Choice(), ad_slots=0, organic_slots=5)
    u = UserPersona("U1")
    qr = mkt.run_query(u, prods[0].title, np.random.default_rng(0), correlation_id="R2")
    assert all(a.slot_type == "organic" for a in qr.actions)
    assert qr.total_charged == 0.0


def test_budget_exhaustion_stops_ads():
    prods = synth_catalog(30, 6, seed=0)
    mkt = Marketplace("mkt", prods, _Choice(), ad_slots=3, organic_slots=4)
    p = prods[0]
    mkt.upsert_campaign(CampaignSpec("c0", "s0", (p.product_id,), (KeywordBid(p.title.split()[0], 1.0),)))
    mkt.set_controls(BidControls("c0", daily_budget=0.0))    # no budget
    cands = mkt._registry.candidates(p.title.split()[0])
    assert cands == []    # exhausted → not a candidate
