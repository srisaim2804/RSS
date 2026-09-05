"""Real-time-bidding contracts (used only when ad_sourcing = 'rtb')."""
from __future__ import annotations

from dataclasses import dataclass

from .definitions import UserPersona


@dataclass(frozen=True)
class BidRequest:
    correlation_id: str
    query: str
    # only the observable user features are shared with the seller in RTB
    user_segment: str
    device_type: str
    n_slots: int = 4


@dataclass(frozen=True)
class BidResponse:
    campaign_id: str
    seller_id: str
    product_id: str
    bid_amount: float

    @staticmethod
    def observable_user(user: UserPersona) -> tuple[str, str]:
        return user.segment, user.observed.device_type
