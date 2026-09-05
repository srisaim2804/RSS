"""Shared data contracts that cross party boundaries (the wire schema).

Three tiers:
  * definitions   — party-owned inputs (UserPersona, Product, CampaignSpec, BidControls)
  * projections   — what one party reveals to another (SlotObservation, ObservationPage)
  * outcomes      — the journal / wire schema for events (UserAction, QueryResult,
                    SettleResult, ActionEvent, Trace)

Note: ``ProductScore`` (ctr/cvr/relevance latents) is deliberately NOT here — it stays
private to rss-mplc. Only its platform-revealed fields surface on ``SlotObservation``.
"""
from .definitions import (
    ObservedFeatures, HiddenFeatures, UserPersona,
    Product, KeywordBid, CampaignSpec, BidControls,
)
from .projections import SlotObservation, ObservationPage
from .outcomes import UserAction, SettleResult, QueryResult, ActionEvent
from .trace import Trace, new_correlation_id
from .ads import BidRequest, BidResponse

__all__ = [
    "ObservedFeatures", "HiddenFeatures", "UserPersona",
    "Product", "KeywordBid", "CampaignSpec", "BidControls",
    "SlotObservation", "ObservationPage",
    "UserAction", "SettleResult", "QueryResult", "ActionEvent",
    "Trace", "new_correlation_id",
    "BidRequest", "BidResponse",
]
