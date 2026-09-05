"""Quality-screening regulator (platform-side ad policy)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Regulator:
    min_quality: float = 0.0     # drop ad candidates below this relevance/quality
