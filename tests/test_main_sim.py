"""`python -m magnet_embed.main_sim` — simulator entry point (C13 refactor)."""

from __future__ import annotations

from pathlib import Path

import pytest

from magnet_embed import main_sim

SAMPLE = Path(__file__).parent / "data" / "sample.gcode"


def test_headless_success():
    assert main_sim.main([str(SAMPLE)]) == 0


def test_headless_confirm_abort_returns_1():
    assert main_sim.main([str(SAMPLE), "--confirm", "abort"]) == 1


def test_needs_a_file_without_gui():
    with pytest.raises(SystemExit):
        main_sim.main([])


def test_gui_path_launches_panel(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(
        "magnet_embed.ui.panel.run_gui", lambda c: seen.setdefault("c", c)
    )
    assert main_sim.main(["--gui", str(SAMPLE)]) == 0
    assert seen["c"].gcode_path is not None
