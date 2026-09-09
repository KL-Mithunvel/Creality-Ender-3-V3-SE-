"""Root `python main.py` — mode dispatch (C13)."""

from __future__ import annotations

from pathlib import Path

import pytest

import main as root_main
from magnet_embed.links.dispenser_sim import SimDispenser
from magnet_embed.links.printer_sim import SimPrinter

SAMPLE = Path(__file__).parent / "data" / "sample.gcode"


@pytest.fixture
def no_gui(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(
        "magnet_embed.ui.panel.run_gui", lambda c: seen.setdefault("controller", c)
    )
    return seen


@pytest.fixture
def fake_serial(monkeypatch):
    monkeypatch.setattr(
        "magnet_embed.links.printer_serial.SerialPrinter", lambda *a, **k: SimPrinter()
    )
    monkeypatch.setattr(
        "magnet_embed.links.dispenser_serial.SerialDispenser",
        lambda *a, **k: SimDispenser(),
    )


def test_default_mode_is_sim(no_gui):
    assert root_main.main([]) == 0
    assert isinstance(no_gui["controller"].printer, SimPrinter)


def test_sim_ping(capsys):
    assert root_main.main(["--sim", "--ping"]) == 0
    out = capsys.readouterr().out
    assert "printer OK" in out and "dispenser OK" in out


def test_headless_run_completes():
    assert root_main.main(["--sim", "--no-gui", str(SAMPLE)]) == 0


def test_headless_without_a_file_errors(capsys):
    with pytest.raises(SystemExit):
        root_main.main(["--sim", "--no-gui"])


def test_printer_mode_has_no_dispenser(no_gui, monkeypatch):
    monkeypatch.setattr(
        "magnet_embed.links.printer_serial.SerialPrinter", lambda *a, **k: SimPrinter()
    )
    monkeypatch.setattr(
        "magnet_embed.links.dispenser_serial.SerialDispenser",
        lambda *a, **k: pytest.fail("no dispenser in --printer mode"),
    )
    assert root_main.main(["--printer"]) == 0
    assert no_gui["controller"].dispenser is None


def test_hardware_ping(fake_serial, capsys):
    assert root_main.main(["--hardware", "--ping"]) == 0
    assert "dispenser OK" in capsys.readouterr().out


def test_hardware_no_dispenser_flag(fake_serial, no_gui, monkeypatch):
    monkeypatch.setattr(
        "magnet_embed.links.dispenser_serial.SerialDispenser",
        lambda *a, **k: pytest.fail("built despite --no-dispenser"),
    )
    assert root_main.main(["--hardware", "--no-dispenser"]) == 0
    assert no_gui["controller"].dispenser is None


def test_conflicting_mode_flags_rejected():
    with pytest.raises(SystemExit):
        root_main.main(["--sim", "--printer"])
