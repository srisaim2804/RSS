"""Enforce the one-way dependency: core code must never import `contrib/`.
(contrib may import core; not the reverse.) Repo-agnostic."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
_IMPORT_CONTRIB = re.compile(r"^\s*(from|import)\s+\S*contrib", re.M)


def test_core_never_imports_contrib():
    offenders = []
    for py in SRC.rglob("*.py"):
        if "contrib" in py.parts:          # the contrib package itself is exempt
            continue
        if _IMPORT_CONTRIB.search(py.read_text()):
            offenders.append(str(py.relative_to(SRC)))
    assert not offenders, f"core files import contrib (forbidden): {offenders}"
