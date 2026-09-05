"""Party interfaces (structural Protocols). Concrete impls live in the party repos
and self-register via entry points; the harness resolves them from config."""
from .services import (
    MarketplaceService, ChoiceModel, SellerPolicy,
    KnowledgeProvider, CampaignRegistry, BidderService,
    MetricsSink, SearchIndex, EventStore,
)
from .agent import Agent, Strategy, WorldView

__all__ = [
    "MarketplaceService", "ChoiceModel", "SellerPolicy",
    "KnowledgeProvider", "CampaignRegistry", "BidderService",
    "MetricsSink", "SearchIndex", "EventStore",
    "Agent", "Strategy", "WorldView",
]
