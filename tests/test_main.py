"""C8 full-hardware entry point — runs without the Arduino."""

from __future__ import annotations

import pytest

from magnet_embed import main as main_mod
from magnet_embed.exceptions import DispenserError
from magnet_embed.links.printer_sim import SimPrinter


class FakeDispenser:
    """Raises on connect() like SerialDispenser with no Uno attached."""

    def __init__(self, *a, **k):
        pass

    def connect(self):
        raise DispenserError("cannot open COM4: not found")


@pytest.fixture
def sim_printer(monkeypatch):
    made: list[SimPrinter] = []

    def factory(*a, **k):
        p = SimPrinter()
        made.append(p)
        return p

    monkeypatch.setattr(main_mod, "SerialPrinter", factory)
    return made


@pytest.fixture
def no_gui(monkeypatch):
    seen: dict = {}
    import magnet_embed.ui.panel as panel_mod

    monkeypatch.setattr(panel_mod, "run_gui", lambda c: seen.setdefault("controller", c))
    return seen


def test_ping_no_dispenser_skips_the_uno(sim_printer, monkeypatch, capsys):
    monkeypatch.setattr(
        main_mod, "SerialDispenser",
        lambda *a, **k: pytest.fail("SerialDispenser built despite --no-dispenser"),
    )
    rc = main_mod.main(["--ping", "--no-dispenser"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "dispenser SKIPPED" in out
    assert "printer OK" in out


def test_ping_reports_dispenser_failure(sim_printer, monkeypatch, capsys):
    monkeypatch.setattr(main_mod, "SerialDispenser", FakeDispenser)
    rc = main_mod.main(["--ping"])
    assert rc == 1
    assert "dispenser FAIL" in capsys.readouterr().err


def test_gui_starts_even_when_the_uno_is_absent(sim_printer, no_gui, monkeypatch):
    monkeypatch.setattr(main_mod, "SerialDispenser", FakeDispenser)
    rc = main_mod.main([])
    assert rc == 0
    ctl = no_gui["controller"]
    assert ctl.dispenser is None                  # degraded cleanly
    assert ctl.dispenser_optional is True


def test_no_dispenser_flag_builds_controller_with_none(sim_printer, no_gui, monkeypatch):
    monkeypatch.setattr(
        main_mod, "SerialDispenser",
        lambda *a, **k: pytest.fail("SerialDispenser built despite --no-dispenser"),
    )
    rc = main_mod.main(["--no-dispenser"])
    assert rc == 0
    assert no_gui["controller"].dispenser is None
