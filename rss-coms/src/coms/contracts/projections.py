"""Observable projections — what the platform reveals to the user/choice model.

The marketplace projects its internal ``SourcedPage``/``ResultSlot`` (which carry the
private ``ProductScore`` latents) down to these observable-only fields. The choice model
reads *only* these, plus whatever it probes via ``KnowledgeProvider``.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SlotObservation:
    position: int
    slot_type: str                 # ad | organic
    product_id: str
    title: str
    price: float
    rating: float
    brand: str
    relevance: float               # platform-revealed relevance (not the raw score)
    is_sponsored: bool = False
    badges: tuple[str, ...] = ()   # e.g. "best_seller"
    # auction bookkeeping the platform needs for settlement (not user-observable
    # signal, but travels with the slot so settlement can price it):
    campaign_id: str | None = None
    seller_id: str | None = None
    cpc: float = 0.0


@dataclass(frozen=True)
class ObservationPage:
    query: str
    slots: tuple[SlotObservation, ...] = field(default_factory=tuple)

    @property
    def ad_slots(self) -> tuple[SlotObservation, ...]:
        return tuple(s for s in self.slots if s.slot_type == "ad")

    @property
    def organic_slots(self) -> tuple[SlotObservation, ...]:
        return tuple(s for s in self.slots if s.slot_type == "organic")
