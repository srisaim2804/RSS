"""rss-coms — commons for the RSS marketplace simulation.

Leaf package: contracts, interfaces, infra/registry, health, correlated event log,
transport, and the simulation harness. The three party repos (rss-usim, rss-mplc,
rss-slrs) depend only on this and self-register via entry points.
"""
from . import contracts, interfaces, infra, health, trace, transport, harness

__all__ = ["contracts", "interfaces", "infra", "health", "trace", "transport", "harness"]
__version__ = "0.1.0"
