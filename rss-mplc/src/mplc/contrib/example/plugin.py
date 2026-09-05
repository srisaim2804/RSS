"""Example contrib for rss-mplc: a knowledge-provider variant.

Registers under the `knowledge` family with a `contrib:` name. The marketplace resolves
its knowledge backend by name, so selecting it is config-only:
`[[marketplaces]] knowledge = "contrib:optimistic"`.
"""
from coms.infra import register


class OptimisticKnowledge:
    """Always reports high brand trust/sentiment — a demo alternative backend."""

    def brand_perception(self, brand: str) -> dict:
        return {"trust": 0.9, "sentiment": 0.5}


register("knowledge", "contrib:optimistic", lambda cfg: OptimisticKnowledge())
