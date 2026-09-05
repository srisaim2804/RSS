"""Auto-discovers contrib subpackages and imports each `<contrib>.<name>.plugin`,
quarantining any that fail so one broken contribution can't take down its siblings.

This module is the `rss.contrib` entry point; importing it runs discovery.
"""
from __future__ import annotations

import pkgutil

from coms.infra import safe_import

from . import __name__ as _PKG, __path__ as _PATH


def _discover() -> None:
    for m in pkgutil.iter_modules(_PATH):
        if m.ispkg and not m.name.startswith("_"):
            safe_import(f"{_PKG}.{m.name}.plugin")


_discover()
