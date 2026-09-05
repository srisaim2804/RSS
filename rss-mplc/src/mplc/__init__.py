"""rss-mplc — marketplace: search, ranking, sponsored-ad auction, hosted campaigns,
knowledge (brand_perception), correlated event emission, platform agents."""
from .marketplace import Marketplace
from .ads import HostedCampaignRegistry
from .knowledge import BrandPerceptionProvider
from .auction import run_auction
from .scoring import ProductScore, score_product
from .agent import PlatformAgent

__all__ = ["Marketplace", "HostedCampaignRegistry", "BrandPerceptionProvider",
           "run_auction", "ProductScore", "score_product", "PlatformAgent"]
__version__ = "0.1.0"
