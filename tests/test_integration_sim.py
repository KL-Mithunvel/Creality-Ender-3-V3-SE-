"""End-to-end: a full sim run through the Controller, sentinel, insert, resume, EOF."""

from __future__ import annotations

import time
from pathlib import Path

from magnet_embed.app import Controller
from magnet_embed.links.dispenser_sim import SimDispenser
from magnet_embed.links.printer_sim import SimPrinter

SAMPLE = Path(__file__).parent / "data" / "sample.gcode"


def _wait(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_end_to_end_sim_run_with_runlog(config, tmp_path):
    printer = SimPrinter()
    dispenser = SimDispenser()
    ctl = Controller(printer, dispenser, config, log_dir=tmp_path)
    ctl.connect()
    ctl.load_gcode(SAMPLE)
    ctl.start_run()

    done = None
    deadline = time.time() + 5.0
    while done is None and time.time() < deadline:
        for kind, payload in ctl.poll_events():
            if kind == "prompt":
                ctl.answer_prompt("success")
            elif kind == "done":
                done = payload
            elif kind == "error":
                raise AssertionError(f"run errored: {payload}")
        time.sleep(0.02)

    assert done is not None, "run never finished"
    assert done["sentinels"] == 1
    assert _wait(lambda: not ctl.running)

    st = printer.query_state()
    assert (st.x, st.y, st.z) == (80.0, 80.0, 8.0)   # last move in the fixture
    assert st.nozzle_target == 0                      # M104 S0 at the end
    assert dispenser.count == 1

    logs = list(Path(tmp_path).glob("*.log"))
    assert len(logs) == 1
    text = logs[0].read_text()
    assert "MAGNET_INSERT" in text
    assert "insert sequence complete" in text
    assert text.rstrip().endswith("=== END SUMMARY ===")
    assert "lines sent:" in text and "errors: none" in text


def test_end_to_end_abort_is_reported_and_logged(config, tmp_path):
    ctl = Controller(SimPrinter(), SimDispenser(), config, log_dir=tmp_path)
    ctl.connect()
    ctl.load_gcode(SAMPLE)
    ctl.start_run()

    err = None
    deadline = time.time() + 5.0
    while err is None and time.time() < deadline:
        for kind, payload in ctl.poll_events():
            if kind == "prompt":
                ctl.answer_prompt("abort")
            elif kind == "error":
                err = payload
        time.sleep(0.02)

    assert err is not None and "abort" in str(err).lower()
    assert _wait(lambda: not ctl.running)
    assert ctl.printer.query_state().nozzle_target == 0   # abort turned the nozzle off
