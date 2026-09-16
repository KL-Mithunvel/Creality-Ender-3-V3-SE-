import threading
from pathlib import Path

import pytest

from magnet_embed.exceptions import ResendRequested, SentinelNotFound
from magnet_embed.gcode.runner import GcodeRunner
from magnet_embed.gcode.util import strip_line_number
from magnet_embed.links.printer_sim import SimPrinter
from magnet_embed.state import MagnetInsert, PrinterState

SAMPLE = Path(__file__).parent / "data" / "sample.gcode"


def _make(config, gcode_path=SAMPLE):
    printer = SimPrinter()
    printer.connect()
    calls: list[MagnetInsert] = []
    runner = GcodeRunner(printer, gcode_path, calls.append, config)
    return printer, runner, calls


def test_streams_to_completion_and_detects_sentinel(config):
    printer, runner, calls = _make(config)
    runner.run()
    assert runner.finished
    assert runner.sentinels_seen == 1
    assert len(calls) == 1 and isinstance(calls[0], MagnetInsert)
    assert calls[0].pocket_xy == (60.0, 60.0)
    assert calls[0].shear_dir == "+X"


def test_sentinel_line_not_forwarded_comments_skipped(config):
    printer, runner, _ = _make(config)
    runner.run()
    assert not any("MAGNET_INSERT" in line for line in printer.sent)
    assert not any(line.strip().startswith(";") for line in printer.sent)
    # every real command line was sent exactly once
    real_cmds = [
        ln.strip()
        for ln in SAMPLE.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith(";")
    ]
    assert runner.sent_lines == len(real_cmds)


def test_final_printer_state_reflects_the_stream(config):
    printer, runner, _ = _make(config)
    runner.run()
    st = printer.query_state()
    assert (st.x, st.y) == (80.0, 80.0)   # last move in the fixture
    assert st.nozzle_target == 0          # M104 S0 at the end


def test_pause_blocks_progress_then_resume_finishes(config):
    printer, runner, _ = _make(config)
    runner.pause()
    worker = threading.Thread(target=runner.run)
    worker.start()
    worker.join(timeout=0.3)
    assert worker.is_alive()
    assert runner.sent_lines == 0
    runner.resume()
    worker.join(timeout=2.0)
    assert not worker.is_alive()
    assert runner.finished


def test_cancel_stops_the_run(config):
    printer, runner, _ = _make(config)
    runner.cancel()
    runner.run()
    assert not runner.finished
    assert runner.sent_lines == 0


def test_require_sentinel_errors_when_absent(config, tmp_path):
    cfg = {**config, "gcode": {**config["gcode"], "require_sentinel": True}}
    g = tmp_path / "no_sentinel.gcode"
    g.write_text("G28\nG90\nG1 X10 Y10\n", encoding="utf-8")
    _, runner, _ = _make(cfg, g)
    with pytest.raises(SentinelNotFound):
        runner.run()


def test_pause_commands_are_not_forwarded(config, tmp_path):
    src = tmp_path / "p.gcode"
    src.write_text(
        "G90\n;LAYER:0\nG1 Z0.2\nG1 X10 Y10 E1\n"
        "M0 ; slicer pause\n"
        ";MAGNET_INSERT X10 Y10 Z0.2 S+X\n"
        "G1 X20 Y20 E2\n",
        encoding="utf-8",
    )
    printer, runner, calls = _make(config, src)
    runner.run()
    assert runner.pauses_skipped == 1
    assert not any(ln.strip().upper().startswith("M0") for ln in printer.sent)
    assert len(calls) == 1                         # the sentinel still fired


# --- C29: line numbers / checksum / resend buffer; M420 resend after G28 --

def _numbered(config):
    return {**config, "gcode": {**config["gcode"], "use_line_numbers": True}}


def test_use_line_numbers_runs_end_to_end(config):
    """The whole sample file streams correctly with numbering on - same
    outcome as the plain-line default, just a different wire format."""
    printer, runner, calls = _make(_numbered(config))
    runner.run()
    assert runner.finished
    assert runner.sentinels_seen == 1
    assert len(calls) == 1
    st = printer.query_state()
    assert (st.x, st.y) == (80.0, 80.0)              # same final position as the plain test
    assert printer.sent[0].startswith("N0 M110 N0*")  # counter reset, sent first
    assert any(strip_line_number(s) == "G90" for s in printer.sent)


class _ResendOnceLink:
    """Minimal fake `PrinterLink`: acks every line, except the first time it
    sees `trigger_bare` (matched on the bare command, ignoring the N/checksum
    wrapper) it raises `ResendRequested(resend_from)` instead - once only, so
    the replay itself succeeds."""

    def __init__(self, trigger_bare: str, resend_from: int) -> None:
        self.sent: list[str] = []
        self._trigger = trigger_bare
        self._resend_from = resend_from
        self._triggered = False
        self._pending = ""

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def send_line(self, line: str) -> None:
        self.sent.append(line)
        self._pending = line

    def wait_ok(self, timeout_s=None) -> str:
        if not self._triggered and strip_line_number(self._pending) == self._trigger:
            self._triggered = True
            raise ResendRequested(self._resend_from)
        return "ok"

    def query_state(self) -> PrinterState:
        return PrinterState()


def test_resend_is_replayed_from_the_requested_line(config, tmp_path):
    g = tmp_path / "tiny.gcode"
    g.write_text("G90\nG1 X10 Y10 F1200\nG1 X20 Y20 F1200\n", encoding="utf-8")
    link = _ResendOnceLink(trigger_bare="G1 X10 Y10 F1200", resend_from=1)
    runner = GcodeRunner(link, g, lambda mi: None, _numbered(config))
    runner.run()
    assert runner.finished
    bare = [strip_line_number(s) for s in link.sent]
    assert bare[0] == "M110 N0"
    assert bare[1:] == [
        "G90", "G1 X10 Y10 F1200",              # first attempt - N2 triggers the resend
        "G90", "G1 X10 Y10 F1200",              # replayed from N1 through the failed N2
        "G1 X20 Y20 F1200",                     # streaming continues normally
    ]


def test_resend_too_far_back_is_fatal(config, tmp_path):
    """A resend for a line the buffer no longer holds (evicted - the cap is
    64, `_RESEND_BUFFER`) can't be serviced, same as plain-line streaming."""
    g = tmp_path / "many.gcode"
    g.write_text(("G4 P1\n" * 65) + "G4 P2\n", encoding="utf-8")  # N1..N65, then N66
    link = _ResendOnceLink(trigger_bare="G4 P2", resend_from=1)   # N1 is long evicted by N66
    runner = GcodeRunner(link, g, lambda mi: None, _numbered(config))
    with pytest.raises(ResendRequested):
        runner.run()


def test_resend_leveling_after_home_resends_m420(config, tmp_path):
    g = tmp_path / "home.gcode"
    g.write_text("G28\nG1 X10 Y10\n", encoding="utf-8")
    cfg = {**config, "gcode": {**config["gcode"], "resend_leveling_after_home": True}}
    printer, runner, _ = _make(cfg, g)
    runner.run()
    assert printer.sent[:2] == ["G28", "M420 S1"]


def test_resend_leveling_after_home_off_by_default(config, tmp_path):
    g = tmp_path / "home.gcode"
    g.write_text("G28\nG1 X10 Y10\n", encoding="utf-8")
    printer, runner, _ = _make(config, g)
    runner.run()
    assert "M420 S1" not in printer.sent
