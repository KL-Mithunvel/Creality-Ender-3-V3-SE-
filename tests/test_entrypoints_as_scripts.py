"""The entry-point files must run as bare scripts too (IDE "Run file"), not only
`python -m ...`. Regression guard for the relative-import ImportError.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SCRIPTS = [
    ROOT / "main.py",
    ROOT / "magnet_embed" / "main.py",
    ROOT / "magnet_embed" / "main_printer.py",
    ROOT / "magnet_embed" / "main_sim.py",
]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: str(p.relative_to(ROOT)))
def test_runs_as_a_bare_script(script):
    r = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "usage:" in r.stdout.lower()
