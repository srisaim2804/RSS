"""Base agent abstractions shared by all parties."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class WorldView:
    """Read-only snapshot handed to an agent each round."""
    round_idx: int = 0
    metrics: dict = field(default_factory=dict)


class Strategy(Protocol):
    def propose(self, *args, **kwargs): ...


class Agent(Protocol):
    def step(self, world: WorldView) -> None: ...
    def observe(self, world: WorldView) -> None: ...
