"""Per-party welfare accounting (spans all three parties → lives in commons)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SellerUtility:
    seller_id: str
    gross_revenue: float = 0.0
    ad_spend: float = 0.0
    cogs: float = 0.0
    value_created: float = 0.0
    purchases: int = 0

    @property
    def profit(self) -> float:
        return self.gross_revenue - self.cogs - self.ad_spend

    @property
    def roas(self) -> float:
        return self.gross_revenue / self.ad_spend if self.ad_spend else 0.0

    @property
    def acos(self) -> float:
        return self.ad_spend / self.gross_revenue if self.gross_revenue else 0.0


@dataclass
class UserUtility:
    user_id: str
    segment: str = "general"
    surplus: float = 0.0
    purchases: int = 0


@dataclass
class PlatformHealth:
    marketplace_id: str
    ad_revenue: float = 0.0
    value_created: float = 0.0
    impressions: int = 0

    @property
    def social_welfare(self) -> float:
        return self.value_created


class UtilityLedger:
    """Accumulates user / seller / platform surplus across a run."""

    def __init__(self, marketplace_id: str = "mkt") -> None:
        self.marketplace_id = marketplace_id
        self._sellers: dict[str, SellerUtility] = {}
        self._users: dict[str, UserUtility] = {}
        self.platform = PlatformHealth(marketplace_id)
        self.sessions = 0

    def _seller(self, sid: str) -> SellerUtility:
        return self._sellers.setdefault(sid, SellerUtility(sid))

    def _user(self, uid: str, segment: str) -> UserUtility:
        u = self._users.get(uid)
        if u is None:
            u = self._users[uid] = UserUtility(uid, segment)
        return u

    def record(self, *, user_id: str, segment: str, seller_id: str | None,
               charged: float, revenue: float, cogs: float,
               user_surplus: float, value_created: float,
               impression: bool) -> None:
        if impression:
            self.platform.impressions += 1
        self.platform.ad_revenue += charged
        self.platform.value_created += value_created
        u = self._user(user_id, segment)
        u.surplus += user_surplus
        if revenue > 0:
            u.purchases += 1
        if seller_id is not None:
            s = self._seller(seller_id)
            s.gross_revenue += revenue
            s.ad_spend += charged
            s.cogs += cogs
            s.value_created += value_created
            if revenue > 0:
                s.purchases += 1

    def record_session(self) -> None:
        self.sessions += 1

    def sellers(self) -> list[SellerUtility]:
        return list(self._sellers.values())

    def users(self) -> list[UserUtility]:
        return list(self._users.values())
