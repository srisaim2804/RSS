"""Minimal example: register a trivial component under a contrib name.

Demonstrates the mechanism; copy `example/` to a new folder and register something real.
"""
from coms.infra import register


def _make(cfg):
    return {"msg": "hello from coms contrib", "cfg": cfg}


register("demo", "contrib:hello", _make)
