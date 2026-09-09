"""`magnet_embed.entry` — shared link wiring, ping, headless run (C13)."""

from __future__ import annotations

from pathlib import Path

import pytest

from magnet_embed import entry
from magnet_embed.links.dispenser_sim import SimDispenser
from magnet_embed.links.printer_sim import SimPrinter

SAMPLE = Path(__file__).parent / "data" / "sample.gcode"


def test_build_links_sim_pair(config):
    printer, dispenser = entry.build_links("sim", config)
    assert isinstance(printer, SimPrinter)
    assert isinstance(dispenser, SimDispenser)


def test_build_links_sim_without_dispenser(config):
    printer, dispenser = entry.build_links("sim", config, with_dispenser=False)
    assert isinstance(printer, SimPrinter)
    assert dispenser is None


def test_build_links_printer_mode_has_no_dispenser(config, monkeypatch):
    monkeypatch.setattr(
        "magnet_embed.links.printer_serial.SerialPrinter", lambda *a, **k: SimPrinter()
    )
    monkeypatch.setattr(
        "magnet_embed.links.dispenser_serial.SerialDispenser",
        lambda *a, **k: pytest.fail("dispenser built in printer mode"),
    )
    _printer, dispenser = entry.build_links("printer", config)
    assert dispenser is None


def test_build_links_hardware_builds_both(config, monkeypatch):
    monkeypatch.setattr(
        "magnet_embed.links.printer_serial.SerialPrinter", lambda *a, **k: SimPrinter()
    )
    made: dict = {}
    monkeypatch.setattr(
        "magnet_embed.links.dispenser_serial.SerialDispenser",
        lambda *a, **k: made.setdefault("d", SimDispenser()),
    )
    _printer, dispenser = entry.build_links("hardware", config)
    assert dispenser is made["d"]


def test_build_links_rejects_unknown_mode(config):
    with pytest.raises(ValueError):
        entry.build_links("bogus", config)


def test_ping_reports_both(config, capsys):
    printer, dispenser = entry.build_links("sim", config)
    assert entry.ping(printer, dispenser) == 0
    out = capsys.readouterr().out
    assert "printer OK" in out and "dispenser OK" in out


def test_ping_skips_absent_dispenser(config, capsys):
    printer, _ = entry.build_links("sim", config, with_dispenser=False)
    assert entry.ping(printer, None) == 0
    assert "dispenser SKIPPED" in capsys.readouterr().out


def test_run_headless_streams_and_inserts(config):
    printer, dispenser = entry.build_links("sim", config, command_delay=0.0)
    assert entry.run_headless(printer, dispenser, config, SAMPLE, confirm="success") == 0
    assert dispenser.count == 1


def test_run_headless_abort_returns_1(config):
    printer, dispenser = entry.build_links("sim", config, command_delay=0.0)
    assert entry.run_headless(printer, dispenser, config, SAMPLE, confirm="abort") == 1
