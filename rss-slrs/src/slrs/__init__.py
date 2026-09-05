"""rss-slrs — seller simulation: sampling, campaign management, bidding/pacing,
seller agents, and the RTB bidder."""
from .sellers import Seller, sample_sellers
from .campaigns import build_campaigns
from .policy import SellerFleet
from .bidder import RTBBidder
from .agent import SellerAgent

__all__ = ["Seller", "sample_sellers", "build_campaigns", "SellerFleet",
           "RTBBidder", "SellerAgent"]
__version__ = "0.1.0"
