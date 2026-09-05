"""The seams that become RPC/network boundaries after the split."""
from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

import numpy as np

from coms.contracts import (
    UserPersona, ObservationPage, QueryResult, ActionEvent,
    CampaignSpec, BidControls, BidRequest, BidResponse,
)


@runtime_checkable
class MarketplaceService(Protocol):
    """The marketplace as seen by the harness. In-process or remote behind the
    identical Protocol."""
    id: str

    def run_query(self, user: UserPersona, query: str, rng: np.random.Generator, *,
                  correlation_id: str | None = None) -> QueryResult: ...

    def run_queries_batch(self, items: Sequence[tuple], rng: np.random.Generator) -> list[QueryResult]: ...

    def reset_day(self) -> None: ...

    def upsert_campaign(self, spec: CampaignSpec) -> None: ...

    def set_controls(self, controls: BidControls) -> None: ...

    def snapshot(self) -> dict: ...


@runtime_checkable
class ChoiceModel(Protocol):
    """User behaviour. Consumes the platform's observable projection + probes knowledge."""
    def sample(self, user: UserPersona, page: ObservationPage,
               knowledge: "KnowledgeProvider", rng: np.random.Generator,
               position_decay: float = 0.7) -> list: ...


@runtime_checkable
class KnowledgeProvider(Protocol):
    """Served by rss-mplc from a knowledge store; probed by the choice model.
    v1 exposes brand_perception only (issue #41 decision)."""
    def brand_perception(self, brand: str) -> dict: ...   # {trust: 0-1, sentiment: -1..1}


@runtime_checkable
class SellerPolicy(Protocol):
    """A seller *fleet* — all of one plugin's sellers/campaigns and their bidding.
    Registered under family 'seller_source' in rss-slrs."""
    def initial_campaigns(self) -> tuple[list[CampaignSpec], list[BidControls]]: ...
    def step(self, round_idx: int, snapshot: dict) -> list[BidControls]: ...
    def observe(self, snapshot: dict) -> None: ...
    def bidder(self) -> "BidderService | None": ...   # non-None only for RTB


@runtime_checkable
class CampaignRegistry(Protocol):
    """Hosted-campaign model: the ad lives on the platform."""
    def upsert_campaign(self, spec: CampaignSpec) -> None: ...
    def set_controls(self, controls: BidControls) -> None: ...
    def candidates(self, query: str) -> list: ...


@runtime_checkable
class BidderService(Protocol):
    """RTB model: the ad lives on the seller, served per request."""
    def bid(self, request: BidRequest) -> list[BidResponse]: ...


@runtime_checkable
class MetricsSink(Protocol):
    def record_action(self, action, outcome: str) -> None: ...
    def get_campaign_metrics(self, campaign_id: str) -> dict: ...


@runtime_checkable
class SearchIndex(Protocol):
    def index(self, products) -> None: ...
    def search(self, query: str, k: int) -> list[dict]: ...


@runtime_checkable
class EventStore(Protocol):
    def write(self, event: ActionEvent) -> None: ...
    def write_many(self, events: list[ActionEvent]) -> None: ...
    def close(self) -> None: ...
