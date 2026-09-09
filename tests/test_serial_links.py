"""C5 serial links, tested against a fake serial transport (no pyserial needed)."""

from __future__ import annotations

from collections import deque

import pytest

from magnet_embed.exceptions import (
    AckTimeout,
    DispenserError,
    PrinterError,
    ResendRequested,
)
from magnet_embed.links._marlin_rx import classify, parse_position, parse_temps
from magnet_embed.links.dispenser_serial import SerialDispenser
from magnet_embed.links.printer_serial import SerialPrinter


# --- fake serial ---------------------------------------------------------

class FakeSerial:
    """`responder(written_line) -> list[str]` supplies the reply lines."""

    def __init__(self, responder):
        self.responder = responder
        self.written: list[str] = []
        self._q: deque[str] = deque()
        self.dtr = False
        self.timeout = 1.0

    def write(self, data):
        text = bytes(data).decode("ascii", "replace").strip()
        self.written.append(text)
        for line in self.responder(text):
            self._q.append(line)
        return len(data)

    def readline(self):
        return (self._q.popleft() + "\n").encode() if self._q else b""

    def reset_input_buffer(self):
        self._q.clear()

    def close(self):
        pass


def _printer(responder, **kw):
    kw.setdefault("connect_settle_s", 0.0)
    return SerialPrinter("COMX", transport_factory=lambda: FakeSerial(responder), **kw)


def _dispenser(responder, **kw):
    kw.setdefault("reset_settle_s", 0.0)
    return SerialDispenser("COMY", transport_factory=lambda: FakeSerial(responder), **kw)


# --- classifier --------------------------------------------------------

@pytest.mark.parametrize(
    "line,kind",
    [
        ("ok", "ok"),
        ("ok T:210.0 /210.0 B:60.0 /60.0", "ok"),
        ("wait", "wait"),
        ("echo:busy: processing", "busy"),
        ("busy: processing", "busy"),
        ("Resend: 5", "resend"),
        ("rs N5", "resend"),
        ("Error:Printer halted. kill() called!", "error"),
        ("//action:paused", "action"),
        ("Marlin 2.1.2", "info"),
        ("echo:SD init fail", "info"),
    ],
)
def test_classify(line, kind):
    assert classify(line).kind == kind


def test_classify_resend_number():
    assert classify("Resend: 12").detail == 12


def test_parse_temps_and_position():
    t = parse_temps("ok T:200.5 /210.0 B:59.0 /60.0")
    assert t["nozzle"] == (200.5, 210.0) and t["bed"] == (59.0, 60.0)
    p = parse_position("X:10.00 Y:20.00 Z:0.40 E:1.50 Count X:800 Y:1600 Z:160")
    assert p == (10.0, 20.0, 0.4, 1.5)
    assert parse_position("ok") is None


# --- SerialPrinter ---------------------------------------------------

def _std_printer_responder(text):
    if text == "M115":
        return ["FIRMWARE_NAME:Marlin 2.1.2 (Creality)", "Cap:EEPROM:1", "ok"]
    if text == "M400":
        return ["ok"]
    if text == "M114":
        return ["X:10.00 Y:20.00 Z:0.40 E:1.50 Count X:800 Y:1600 Z:160", "ok"]
    return ["ok"]


def test_connect_handshake_tolerates_banner():
    p = _printer(_std_printer_responder)
    p.connect()
    assert p.state.connected
    assert "M115" in p._ser.written


def test_query_state_reads_m114():
    p = _printer(_std_printer_responder)
    p.connect()
    st = p.query_state()
    assert (st.x, st.y, st.z, st.e) == (10.0, 20.0, 0.4, 1.5)


def test_modes_tracked_from_outgoing_stream():
    p = _printer(_std_printer_responder)
    p.connect()
    p.command("G91")
    p.command("M83")
    p.command("G1 X5 F1800")
    assert p.state.absolute_xyz is False
    assert p.state.absolute_e is False
    assert p.state.feedrate == 1800.0


def test_busy_extends_the_deadline():
    def responder(text):
        if text == "M115":
            return ["ok"]
        if text == "G28":
            return ["echo:busy: processing", "echo:busy: processing", "ok"]
        return ["ok"]

    p = _printer(responder, ack_timeout_s=0.5)
    p.connect()
    p.command("G28")  # would time out at 0.5 s without the busy reset; replies are instant here


def test_temps_absorbed_from_ok_line():
    def responder(text):
        return ["ok"] if text == "M115" else ["ok T:199.0 /200.0 B:59.5 /60.0"]

    p = _printer(responder)
    p.connect()
    p.command("M105")
    assert p.state.nozzle_temp == 199.0 and p.state.bed_target == 60.0


def test_resend_is_fatal():
    def responder(text):
        return ["ok"] if text == "M115" else ["Resend: 7"]

    p = _printer(responder)
    p.connect()
    with pytest.raises(ResendRequested):
        p.command("G1 X1")


def test_firmware_error_raises():
    def responder(text):
        return ["ok"] if text == "M115" else ["Error:Thermal runaway"]

    p = _printer(responder)
    p.connect()
    with pytest.raises(PrinterError):
        p.command("G1 X1")


def test_ack_timeout():
    def responder(text):
        return ["ok"] if text == "M115" else []

    p = _printer(responder, ack_timeout_s=0.15)
    p.connect()
    with pytest.raises(AckTimeout):
        p.command("G1 X1")


# --- SerialDispenser ------------------------------------------------

def _std_dispenser_responder(text):
    return {
        "PING": ["PONG"],
        "DISPENSE": ["OK DISPENSE"],
        "RESET": ["OK RESET"],
        "STATUS": ["STATUS servo=90 count=3 last=dispense"],
    }.get(text, [])


def test_dispenser_connect_and_ping():
    d = _dispenser(_std_dispenser_responder)
    d.connect()
    assert d.connected and d.ping()


def test_dispenser_connect_ignores_boot_noise_then_pongs():
    state = {"pinged": 0}

    def responder(text):
        if text == "PING":
            state["pinged"] += 1
            return ["garbage boot line"] if state["pinged"] == 1 else ["PONG"]
        return []

    d = _dispenser(responder)
    d.connect()          # first PING gets junk, retries, second gets PONG
    assert d.connected


def test_dispense_ok_and_status():
    d = _dispenser(_std_dispenser_responder)
    d.connect()
    d.dispense()
    d.reset()
    assert d.status() == {"servo": "90", "count": "3", "last": "dispense"}


def test_dispense_error_raises():
    def responder(text):
        if text == "PING":
            return ["PONG"]
        return ["ERR DISPENSE magazine empty"]

    d = _dispenser(responder)
    d.connect()
    with pytest.raises(DispenserError):
        d.dispense()


def test_connect_without_pong_raises():
    d = _dispenser(lambda text: [], ping_timeout_s=0.05)
    with pytest.raises(DispenserError):
        d.connect()


def test_dispense_timeout_raises():
    def responder(text):
        return ["PONG"] if text == "PING" else []

    d = _dispenser(responder, reply_timeout_s=0.15)
    d.connect()
    with pytest.raises(DispenserError):
        d.dispense()
