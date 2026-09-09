"""C7 printer-only entry point (`python -m magnet_embed.main_printer`)."""

from __future__ import annotations

import pytest

from magnet_embed import main_printer
from magnet_embed.exceptions import PrinterConnectionError
from magnet_embed.state import PrinterState


class FakePrinter:
    """Records lifecycle calls; stands in for SerialPrinter."""

    def __init__(self, *args, fail: bool = False, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.fail = fail
        self.calls: list[str] = []

    def connect(self) -> None:
        self.calls.append("connect")
        if self.fail:
            raise PrinterConnectionError("no such port")

    def query_state(self) -> PrinterState:
        self.calls.append("query_state")
        return PrinterState(connected=True, x=1.0, y=2.0, z=3.0, nozzle_temp=25.0)

    def disconnect(self) -> None:
        self.calls.append("disconnect")


@pytest.fixture
def fake_serial(monkeypatch):
    made: list[FakePrinter] = []

    def factory(*args, **kwargs):
        p = FakePrinter(*args, **kwargs)
        made.append(p)
        return p

    monkeypatch.setattr("magnet_embed.links.printer_serial.SerialPrinter", factory)
    return made


def test_ping_ok(fake_serial, capsys):
    rc = main_printer.main(["--ping"])
    assert rc == 0
    assert fake_serial[0].calls == ["connect", "query_state", "disconnect"]
    assert "printer OK" in capsys.readouterr().out


def test_ping_failure_returns_1(fake_serial, monkeypatch, capsys):
    monkeypatch.setattr(
        "magnet_embed.links.printer_serial.SerialPrinter",
        lambda *a, **k: FakePrinter(*a, fail=True, **k),
    )
    rc = main_printer.main(["--ping"])
    assert rc == 1
    assert "printer FAIL" in capsys.readouterr().err


def test_gui_wires_controller_with_no_dispenser(fake_serial, monkeypatch):
    seen: dict = {}

    class SpyController:
        def __init__(self, printer, dispenser, config, **kw):
            seen["printer"] = printer
            seen["dispenser"] = dispenser
            self._loaded = None

        def connect(self) -> None:
            seen["connected"] = True

        def load_gcode(self, path) -> None:
            self._loaded = path

    import magnet_embed.app as app_mod
    import magnet_embed.ui.panel as panel_mod

    monkeypatch.setattr(app_mod, "Controller", SpyController)
    monkeypatch.setattr(panel_mod, "run_gui", lambda c: seen.setdefault("gui", c))

    rc = main_printer.main([])
    assert rc == 0
    assert seen["dispenser"] is None
    assert seen["connected"] is True
    assert seen["printer"] is fake_serial[0]


def test_gui_connect_failure_returns_1(fake_serial, monkeypatch):
    class FailingController:
        def __init__(self, *a, **k):
            pass

        def connect(self) -> None:
            raise PrinterConnectionError("port busy")

    import magnet_embed.app as app_mod

    monkeypatch.setattr(app_mod, "Controller", FailingController)
    assert main_printer.main([]) == 1
