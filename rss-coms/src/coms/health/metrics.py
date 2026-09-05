"""Top-level metric extraction + A/B statistics."""
from __future__ import annotations

import numpy as np

from .ledger import UtilityLedger


def extract_metrics(ledger: UtilityLedger, tracker=None) -> dict:
    """Flatten a ledger (+ optional tracker) into the standard metric dict."""
    sellers = ledger.sellers()
    users = ledger.users()
    platform = ledger.platform
    seller_profit = sum(s.profit for s in sellers)
    gross = sum(s.gross_revenue for s in sellers)
    ad_spend = sum(s.ad_spend for s in sellers)
    user_surplus = sum(u.surplus for u in users)
    sessions = max(ledger.sessions, 1)
    roas = [s.roas for s in sellers if s.ad_spend > 0]
    acos = [s.acos for s in sellers if s.gross_revenue > 0]
    total_welfare = platform.ad_revenue + seller_profit + user_surplus
    m = {
        "platform_revenue": platform.ad_revenue,
        "gross_revenue_total": gross,
        "total_ad_spend": ad_spend,
        "seller_profit_total": seller_profit,
        "seller_roas_mean": float(np.mean(roas)) if roas else 0.0,
        "seller_acos_mean": float(np.mean(acos)) if acos else 0.0,
        "user_surplus_per_session": user_surplus / sessions,
        "social_welfare": platform.social_welfare,
        "total_welfare": total_welfare,
        "impressions": platform.impressions,
        "total_purchases": sum(u.purchases for u in users),
        "n_sellers": len(sellers),
        "n_users": len(users),
    }
    if tracker is not None:
        cms = [tracker.get_campaign_metrics(c) for c in tracker.all_campaigns()]
        if cms:
            m["mean_ctr"] = float(np.mean([c["ctr"] for c in cms]))
            m["mean_cvr"] = float(np.mean([c["cvr"] for c in cms]))
    return m


def bootstrap_ci(data, confidence: float = 0.95, n: int = 2000, seed: int = 0):
    """Percentile bootstrap CI of the mean."""
    x = np.asarray(data, float)
    if x.size == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, x.size, size=(n, x.size))].mean(axis=1)
    lo = (1 - confidence) / 2 * 100
    return (float(np.percentile(means, lo)), float(np.percentile(means, 100 - lo)))


def compare_arms(control, treatment, n: int = 2000, seed: int = 0) -> dict:
    """ATE + bootstrap CI + a rough two-sample significance flag."""
    c, t = np.asarray(control, float), np.asarray(treatment, float)
    ate = float(t.mean() - c.mean()) if c.size and t.size else 0.0
    rng = np.random.default_rng(seed)
    diffs = (t[rng.integers(0, t.size, size=(n, t.size))].mean(axis=1)
             - c[rng.integers(0, c.size, size=(n, c.size))].mean(axis=1)) if c.size and t.size else np.array([0.0])
    lo, hi = float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))
    return {"ate": ate, "ci": (lo, hi), "significant": not (lo <= 0 <= hi)}
