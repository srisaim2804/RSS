from coms.health import UtilityLedger, MetricsTracker, extract_metrics, compare_arms


def test_ledger_and_metrics():
    led = UtilityLedger("mkt")
    led.record_session()
    led.record(user_id="U1", segment="general", seller_id="s1",
               charged=0.5, revenue=20.0, cogs=8.0, user_surplus=5.0,
               value_created=12.0, impression=True)
    m = extract_metrics(led)
    assert m["platform_revenue"] == 0.5
    assert m["seller_profit_total"] == 20.0 - 8.0 - 0.5
    assert m["user_surplus_per_session"] == 5.0
    assert m["total_purchases"] == 1


def test_tracker_ctr_cvr():
    t = MetricsTracker(["c1"])

    class A:
        campaign_id = "c1"; cpc = 0.5; price = 10.0
    t.record_action(A(), "clicked")
    t.record_action(A(), "purchased")
    cm = t.get_campaign_metrics("c1")
    assert cm["clicks"] == 2 and cm["conversions"] == 1
    assert cm["revenue"] == 10.0


def test_compare_arms_detects_shift():
    res = compare_arms([0.0] * 20, [1.0] * 20)
    assert res["ate"] == 1.0 and res["significant"]
