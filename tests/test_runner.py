import threading
from pathlib import Path

import pytest

from magnet_embed.exceptions import SentinelNotFound
from magnet_embed.gcode.runner import GcodeRunner
from magnet_embed.links.printer_sim import SimPrinter
from magnet_embed.state import MagnetInsert

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
