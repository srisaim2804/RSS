"""Per-campaign KPI counters (satisfies the MetricsSink interface)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _Counters:
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    revenue: float = 0.0


class MetricsTracker:
    def __init__(self, campaign_ids: list[str] | None = None) -> None:
        self._c: dict[str, _Counters] = {cid: _Counters() for cid in (campaign_ids or [])}

    def _get(self, cid: str) -> _Counters:
        return self._c.setdefault(cid, _Counters())

    def record_action(self, action, outcome: str) -> None:
        cid = getattr(action, "campaign_id", None)
        if cid is None:
            return
        c = self._get(cid)
        if outcome in ("seen", "clicked", "cart", "purchased"):
            c.impressions += 1
        if outcome in ("clicked", "cart", "purchased"):
            c.clicks += 1
            c.spend += getattr(action, "cpc", 0.0)
        if outcome == "purchased":
            c.conversions += 1
            c.revenue += getattr(action, "price", 0.0)

    def record_organic_sale(self, campaign_id: str, revenue: float) -> None:
        self._get(campaign_id).revenue += revenue

    def get_campaign_metrics(self, campaign_id: str) -> dict:
        c = self._get(campaign_id)
        ctr = c.clicks / c.impressions if c.impressions else 0.0
        cvr = c.conversions / c.clicks if c.clicks else 0.0
        acos = c.spend / c.revenue if c.revenue else 0.0
        roas = c.revenue / c.spend if c.spend else 0.0
        return {"impressions": c.impressions, "clicks": c.clicks,
                "conversions": c.conversions, "spend": c.spend, "revenue": c.revenue,
                "ctr": ctr, "cvr": cvr, "acos": acos, "roas": roas}

    def all_campaigns(self) -> list[str]:
        return list(self._c)
