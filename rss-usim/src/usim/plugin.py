"""Entry-point module (rss.plugins → usim). Importing it registers usim components."""
from __future__ import annotations

from coms.infra import register

from . import choice_model  # noqa: F401  (registers choice_model on import)
from .personas import sample_users


def _user_source(cfg: dict):
    return sample_users(cfg.get("n_users", 50), cfg["products"], cfg.get("seed", 0))


register("user_source", "usim", _user_source)
