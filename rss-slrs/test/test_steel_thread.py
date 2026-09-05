"""Smoke tests: run each steel-thread path so CI guards them from rot."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", ["sample", "campaign", "bid"])
def test_steel_thread_paths(path):
    r = subprocess.run(
        [sys.executable, str(ROOT / "steel_thread" / "run.py"), "--path", path],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
