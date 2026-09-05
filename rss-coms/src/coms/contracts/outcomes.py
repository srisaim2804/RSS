"""Outcomes / event journal — the wire schema for the correlated event log."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UserAction:
    slot: int
    slot_type: str                 # ad | organic
    action: str                    # not_seen | seen | clicked | cart | purchased
    product_id: str
    campaign_id: str | None
    seller_id: str | None
    price: float
    cpc: float = 0.0
    p_seen: float = 0.0
    p_click: float = 0.0
    p_cart: float = 0.0
    p_purchase: float = 0.0


@dataclass(frozen=True)
class SettleResult:
    charged: float = 0.0           # platform revenue (cpc on click)
    revenue: float = 0.0           # seller gross (price on purchase)
    cogs: float = 0.0              # seller cost of goods
    clicked: bool = False
    purchased: bool = False


@dataclass(frozen=True)
class QueryResult:
    query: str
    user_id: str
    correlation_id: str
    actions: tuple[UserAction, ...] = ()
    settle: tuple[SettleResult, ...] = ()
    n_purchased: int = 0
    total_charged: float = 0.0


@dataclass(frozen=True)
class ActionEvent:
    """One row in the correlated event log."""
    correlation_id: str
    tick: int
    party: str                     # user | marketplace | seller
    stage: str                     # search | ad_source | impress | click | purchase | settle …
    user_id: str = ""
    query: str = ""
    product_id: str | None = None
    campaign_id: str | None = None
    seller_id: str | None = None
    slot: int = -1
    slot_type: str = ""
    action: str = ""
    cpc: float = 0.0
    price: float = 0.0
    parent_id: str | None = None
    extra: dict = field(default_factory=dict)
