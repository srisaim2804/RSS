"""Party-owned input definitions."""
from __future__ import annotations

from dataclasses import dataclass, field


# ── User (owned by rss-usim) ──────────────────────────────────────────────────
@dataclass(frozen=True)
class ObservedFeatures:
    """Features the platform can observe about a user."""
    age: int = 30
    device_type: str = "mobile"           # mobile | desktop | tablet
    price_sensitivity: float = 5.0        # 0-10
    ad_susceptibility: float = 5.0        # 0-10
    review_dependency: float = 5.0        # 0-10
    brand_loyalty: float = 0.5            # 0-1
    domain_knowledge: str = "moderate"    # low | moderate | high


@dataclass(frozen=True)
class HiddenFeatures:
    """Latent traits driving the conversion funnel (never leave rss-usim)."""
    true_budget_ceiling: float = 500.0
    impulse_threshold: float = 0.5        # 0-1
    social_proof_weight: float = 0.5      # 0-1
    novelty_bias: float = 0.5             # 0-1
    variety_seeking: float = 0.5          # 0-1


@dataclass(frozen=True)
class UserPersona:
    user_id: str
    segment: str = "general"
    observed: ObservedFeatures = field(default_factory=ObservedFeatures)
    hidden: HiddenFeatures = field(default_factory=HiddenFeatures)
    queries: tuple[str, ...] = ()
    locale: str = "en-US"


# ── Products & campaigns (products owned by rss-slrs catalog; campaigns are
#    defined by rss-slrs but hosted by rss-mplc) ────────────────────────────────
@dataclass(frozen=True)
class Product:
    product_id: str
    title: str
    price: float
    rating: float = 4.0
    brand: str = ""
    seller_id: str = ""
    cogs_unit: float = 0.0
    stock: int = 1_000_000


@dataclass(frozen=True)
class KeywordBid:
    keyword: str
    bid_amount: float
    match_type: str = "broad"             # broad | phrase | exact


@dataclass(frozen=True)
class CampaignSpec:
    """The ad *definition* a seller registers with a marketplace (hosted model)."""
    campaign_id: str
    seller_id: str
    product_ids: tuple[str, ...]
    keyword_bids: tuple[KeywordBid, ...]
    target_segments: tuple[str, ...] = ("general",)
    negative_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class BidControls:
    """The *controls* a seller pushes each round; the campaign object lives platform-side."""
    campaign_id: str
    bid_multiplier: float = 1.0
    daily_budget: float = 100.0
    weekly_budget: float = float("inf")
    pace_mode: str = "even"               # even | front_loaded | oco_ltc
    status: str = "active"                # active | paused
