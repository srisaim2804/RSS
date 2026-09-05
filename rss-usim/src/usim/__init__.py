"""rss-usim — user simulation: personas, query generation, choice model, user agents."""
from .personas import sample_users
from .choice_model import IndependentFunnelChoiceModel
from .agent import UserAgent

__all__ = ["sample_users", "IndependentFunnelChoiceModel", "UserAgent"]
__version__ = "0.1.0"
