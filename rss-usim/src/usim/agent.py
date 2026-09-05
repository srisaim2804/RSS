"""User agent — a thin wrapper that can drive a session (query → observe → refine).

Kept minimal for v1; the choice model carries the behavioural core. This is where an
LLM-backed conversational user agent would live (see rss CLAUDE.md vision).
"""
from __future__ import annotations

from dataclasses import dataclass

from coms.contracts import UserPersona


@dataclass
class UserAgent:
    persona: UserPersona

    def next_query(self, rng) -> str:
        qs = self.persona.queries
        return qs[int(rng.integers(len(qs)))] if qs else "product"
