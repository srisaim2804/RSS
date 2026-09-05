"""Smoke tests: run each steel-thread path so CI guards them from rot.
The steel thread itself stays top-level (`steel_thread/`); this only invokes it."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(path: str):
    return subprocess.run(
        [sys.executable, str(ROOT / "steel_thread" / "run.py"), "--path", path],
        capture_output=True, text=True)


@pytest.mark.parametrize("path", ["trace", "transport"])
def test_steel_thread_local_paths(path):
    r = _run(path)
    assert r.returncode == 0, r.stderr


def test_steel_thread_system():
    # needs the three party packages installed
    pytest.importorskip("usim")
    pytest.importorskip("mplc")
    pytest.importorskip("slrs")
    r = _run("system")
    assert r.returncode == 0, r.stderr
