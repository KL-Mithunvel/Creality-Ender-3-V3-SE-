import time
from pathlib import Path

import pytest

from magnet_embed.app import Controller
from magnet_embed.exceptions import DispenserError
from magnet_embed.links.dispenser_sim import SimDispenser
from magnet_embed.links.printer_sim import SimPrinter

SAMPLE = Path(__file__).parent / "data" / "sample.gcode"


def _wait(cond, timeout=4.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def _pump_until(ctl, kind, *, answer=None, timeout=4.0):
    """Drain events until one of `kind` is seen; answer any prompt with `answer`."""
    seen: list = []
    end = time.time() + timeout
    while time.time() < end:
        for ev in ctl.poll_events():
            seen.append(ev)
            if ev[0] == "prompt" and answer is not None:
                ctl.answer_prompt(answer)
        if any(e[0] == kind for e in seen):
            return seen
        time.sleep(0.02)
    raise AssertionError(f"never saw {kind!r}; saw {[e[0] for e in seen]}")


def _ctl(config, *, delay=0.0):
    ctl = Controller(SimPrinter(command_delay=delay), SimDispenser(), config)
    ctl.connect()
    return ctl


def test_full_run_prompts_then_finishes(config):
    ctl = _ctl(config)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    seen = _pump_until(ctl, "done", answer="success")
    kinds = [e[0] for e in seen]
    assert "prompt" in kinds and "done" in kinds
    assert _wait(lambda: not ctl.running)
    done = next(p for k, p in seen if k == "done")
    assert done["sentinels"] == 1


def test_abort_prompt_emits_error(config):
    ctl = _ctl(config)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    seen = _pump_until(ctl, "error", answer="abort")
    assert any(k == "error" for k, _ in seen)
    assert _wait(lambda: not ctl.running)


def test_insert_emits_phase_events_in_order(config):
    """C26: `_on_sentinel` wires `insert_magnet`'s `on_phase` into the events
    queue so the panel can drive a live view during the insert (see
    `ui/panel.py._sync_live_view`), instead of freezing at the sentinel line."""
    ctl = _ctl(config)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    seen = _pump_until(ctl, "done", answer="success")
    phases = [p["phase"] for k, p in seen if k == "phase"]
    assert phases == [
        "PARK", "DISPENSE", "APPROACH", "PRESS", "SHEAR", "LIFT", "CONFIRM", "RESUME",
    ]
    assert ctl.in_insert is False


def test_jog_when_idle_moves_the_printer(config):
    ctl = _ctl(config)
    ctl.jog("X", 5.0)
    ctl.jog("Y", -2.0)
    st = ctl.printer.query_state()
    assert (st.x, st.y) == (5.0, -2.0)
    assert st.absolute_xyz is True  # restored to G90


def test_jog_rejected_while_running(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.jog("X", 10.0)
    evs = ctl.poll_events()
    assert any(k == "log" and "ignored" in str(p) for k, p in evs)
    _pump_until(ctl, "done", answer="success")


def test_pause_halts_progress_then_resume_finishes(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.pause()
    time.sleep(0.2)
    sent = ctl.runner.sent_lines
    time.sleep(0.2)
    assert ctl.runner.sent_lines == sent          # frozen while paused
    ctl.resume()
    _pump_until(ctl, "done", answer="success")
    assert ctl.runner.finished


def test_cancel_stops_the_run(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.cancel()
    assert _wait(lambda: not ctl.running)
    assert not ctl.runner.finished


def test_cancel_leaves_the_printer_safe(config):
    """C27: after stopping the stream, cancel() retracts, lifts, parks, and
    turns the heaters off (config.cancel.heaters_off, default True)."""
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.cancel()
    assert _wait(lambda: not ctl.running)
    assert _wait(lambda: "M140 S0" in ctl.printer.sent, timeout=6.0)
    sent = ctl.printer.sent
    assert any(s.startswith("G1 E-") for s in sent)                  # retract
    assert "M104 S0" in sent and "M140 S0" in sent                   # heaters off
    park = config["park"]
    assert any(s.startswith(f"G1 X{park['x']:g} Y{park['y']:g}") for s in sent)  # parked


def test_home_runs_on_a_background_thread(config):
    """C27: home()/level_bed()/start_z_calibration() no longer block the
    caller - `_busy` flips True synchronously, other idle actions (and a
    second Home) are refused while it's in flight instead of racing it."""
    ctl = _ctl(config, delay=0.2)
    ctl.home()
    assert ctl.busy                       # set synchronously, before the worker thread runs
    ctl.jog("X", 5.0)                     # refused - busy, not queued
    ctl.home()                            # refused too
    logs = [str(p) for k, p in ctl.poll_events() if k == "log"]
    assert any("ignored - busy" in m for m in logs)
    assert _wait(lambda: not ctl.busy, timeout=4.0)
    assert ctl.printer.sent.count("G28") == 1     # the second Home call never sent anything


def test_set_temp_does_not_block_while_busy(config):
    """C27: set_temp waits at most `_LOCK_WAIT_S` for `_printer_lock`, not
    however long the background Home/Level-Bed/Z-cal command takes - it must
    not relocate the "Tk main loop frozen" problem the background thread
    was added to fix."""
    ctl = _ctl(config, delay=1.0)         # Home holds _printer_lock ~1.0s
    ctl.home()
    time.sleep(0.05)                      # let the background thread acquire the lock
    assert ctl.busy
    t0 = time.time()
    ctl.set_temp("nozzle", 200)
    assert time.time() - t0 < 0.6         # did not wait out Home's full hold
    logs = [str(p) for k, p in ctl.poll_events() if k == "log"]
    assert any("busy" in m.lower() for m in logs)
    assert "M104 S200" not in ctl.printer.sent
    assert _wait(lambda: not ctl.busy, timeout=4.0)


def test_start_run_without_file_is_a_noop(config):
    ctl = _ctl(config)
    ctl.start_run()
    assert not ctl.running
    assert any(k == "log" and "no G-code" in str(p) for k, p in ctl.poll_events())


def test_load_rejected_while_running(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.load_gcode("something_else.gcode")
    assert any(k == "log" and "cannot load" in str(p) for k, p in ctl.poll_events())
    _pump_until(ctl, "done", answer="success")


# --- C8: dispenser optional at connect time ---------------------------

class _BrokenDispenser:
    def connect(self):
        raise DispenserError("cannot open COM4: not found")


def test_optional_dispenser_degrades_to_none(config):
    ctl = Controller(SimPrinter(), _BrokenDispenser(), config, dispenser_optional=True)
    ctl.connect()
    assert ctl.dispenser is None
    assert any(
        k == "log" and "dispenser unavailable" in str(p) for k, p in ctl.poll_events()
    )


def test_required_dispenser_failure_still_raises(config):
    ctl = Controller(SimPrinter(), _BrokenDispenser(), config)  # optional defaults False
    with pytest.raises(DispenserError):
        ctl.connect()


def test_healthy_dispenser_connects_when_optional(config):
    ctl = Controller(SimPrinter(), SimDispenser(), config, dispenser_optional=True)
    ctl.connect()
    assert isinstance(ctl.dispenser, SimDispenser)


# --- C13: raw G-code entry ------------------------------------------

def test_send_command_echoes_reply(config):
    ctl = _ctl(config)
    ctl.send_command("M114")
    events = [(k, str(p)) for k, p in ctl.poll_events()]
    assert ("log", "> M114") in events
    assert any(k == "log" and p.startswith("< ") for k, p in events)


def test_send_command_blank_is_a_noop(config):
    ctl = _ctl(config)
    ctl.poll_events()  # drain the connect events
    before = list(ctl.printer.sent)
    ctl.send_command("   ")
    assert ctl.printer.sent == before
    assert ctl.poll_events() == []


def test_send_command_ignored_while_running(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.send_command("M114")
    assert any(k == "log" and "ignored - busy" in str(p) for k, p in ctl.poll_events())
    _pump_until(ctl, "done", answer="success")


def test_send_command_surfaces_printer_error(config):
    ctl = _ctl(config)

    def boom(_line, timeout_s=None):
        from magnet_embed.exceptions import PrinterError

        raise PrinterError("MAXTEMP triggered")

    ctl.printer.command = boom
    ctl.send_command("M104 S999")
    assert any(k == "error" for k, _ in ctl.poll_events())


# --- C18: idle polling, extrude/retract, progress -------------------

def test_refresh_state_polls_temps_when_idle(config):
    ctl = _ctl(config)
    ctl.poll_events()
    ctl.refresh_state()
    assert "M105" in ctl.printer.sent
    assert any(k == "state" for k, _ in ctl.poll_events())


def test_refresh_state_noop_when_not_connected(config):
    ctl = Controller(SimPrinter(), SimDispenser(), config)   # never connected
    ctl.refresh_state()
    assert ctl.printer.sent == []


def test_refresh_state_allowed_while_running(config):
    """Unlike jog/home/extrude, refresh_state is read-only (M105/M400/M114) so
    it's safe to poll during a normal print - locked against the streaming loop."""
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.refresh_state()
    assert "M105" in ctl.printer.sent
    assert any(k == "state" for k, _ in ctl.poll_events())
    _pump_until(ctl, "done", answer="success")


def test_refresh_state_blocked_during_insert_sequence(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    _pump_until(ctl, "prompt")  # stop right at the confirm prompt; don't answer yet
    before = list(ctl.printer.sent)
    ctl.refresh_state()
    assert ctl.printer.sent == before
    ctl.answer_prompt("success")
    _pump_until(ctl, "done")


def test_extrude_then_retract(config):
    ctl = _ctl(config)
    ctl.extrude(5.0, 300.0)
    ctl.extrude(-2.0, 300.0)
    assert "M83" in ctl.printer.sent
    assert "G1 E5 F300" in ctl.printer.sent
    assert "G1 E-2 F300" in ctl.printer.sent


def test_extrude_ignored_while_running(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    before = list(ctl.printer.sent)
    ctl.extrude(5.0, 300.0)
    assert ctl.printer.sent == before
    _pump_until(ctl, "done", answer="success")


def _boom(_line, timeout_s=None):
    from magnet_embed.exceptions import PrinterError

    raise PrinterError("boom")


def test_level_bed_sends_probe_enable_and_save(config):
    # C27: level_bed() runs on a background thread (`Controller._run_offline`)
    # so the Tk main loop stays responsive for the whole probe - wait for it.
    ctl = _ctl(config)
    ctl.level_bed()
    assert _wait(lambda: not ctl.busy)
    assert ctl.printer.sent[-4:] == ["G28", "G29", "M420 S1", "M500"]


def test_level_bed_ignored_while_running(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    before = list(ctl.printer.sent)
    ctl.level_bed()
    assert ctl.printer.sent == before
    assert any(k == "log" and "ignored" in str(p) for k, p in ctl.poll_events())
    _pump_until(ctl, "done", answer="success")


def test_level_bed_surfaces_printer_error(config):
    ctl = _ctl(config)
    ctl.printer.command = _boom
    ctl.level_bed()
    assert _wait(lambda: not ctl.busy)
    assert any(k == "error" for k, _ in ctl.poll_events())


def test_jog_surfaces_printer_error(config):
    ctl = _ctl(config)
    ctl.printer.command = _boom
    ctl.jog("X", 5.0)
    assert any(k == "error" for k, _ in ctl.poll_events())


def test_home_surfaces_printer_error(config):
    ctl = _ctl(config)
    ctl.printer.command = _boom
    ctl.home()
    assert _wait(lambda: not ctl.busy)
    assert any(k == "error" for k, _ in ctl.poll_events())


def test_extrude_surfaces_printer_error(config):
    ctl = _ctl(config)
    ctl.printer.command = _boom
    ctl.extrude(5.0, 300.0)
    assert any(k == "error" for k, _ in ctl.poll_events())


# --- temp range guard + mid-print temp change ------------------------

def test_set_temp_within_range_sends_command(config):
    ctl = _ctl(config)
    ctl.set_temp("nozzle", 200)
    assert "M104 S200" in ctl.printer.sent


def test_set_temp_rejects_above_max(config):
    ctl = _ctl(config)
    ctl.poll_events()
    before = list(ctl.printer.sent)
    ctl.set_temp("nozzle", 999)
    assert ctl.printer.sent == before
    assert any(k == "error" and "outside" in str(p) for k, p in ctl.poll_events())


def test_set_temp_rejects_below_min(config):
    ctl = _ctl(config)
    ctl.poll_events()
    before = list(ctl.printer.sent)
    ctl.set_temp("bed", -5)
    assert ctl.printer.sent == before
    assert any(k == "error" for k, _ in ctl.poll_events())


def test_set_temp_surfaces_printer_error(config):
    ctl = _ctl(config)
    ctl.printer.command = _boom
    ctl.set_temp("nozzle", 200)
    assert any(k == "error" for k, _ in ctl.poll_events())


def test_set_temp_allowed_while_running(config):
    """Unlike jog/home/extrude, set_temp is not idle-only - it's safe mid-print
    (M104/M140 don't touch motion) and is locked against the streaming loop."""
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.set_temp("nozzle", 200)
    assert "M104 S200" in ctl.printer.sent
    _pump_until(ctl, "done", answer="success")


def test_set_temp_blocked_during_insert_sequence(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    _pump_until(ctl, "prompt")  # stop right at the confirm prompt; don't answer yet
    before = list(ctl.printer.sent)
    ctl.set_temp("nozzle", 200)
    assert ctl.printer.sent == before
    assert any(k == "log" and "insert sequence owns" in str(p) for k, p in ctl.poll_events())
    ctl.answer_prompt("success")
    _pump_until(ctl, "done")


# --- C20: live-print view (toolpath cache + progress_point) --------

def test_load_gcode_caches_a_toolpath(config):
    ctl = _ctl(config)
    assert ctl.toolpath is None
    ctl.load_gcode(SAMPLE)
    assert ctl.toolpath is not None
    assert ctl.toolpath.layer_count > 0


def test_progress_point_none_before_a_file_is_loaded(config):
    ctl = _ctl(config)
    assert ctl.progress_point is None


def test_progress_point_tracks_progress_during_a_run(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.progress[0] > 0)
    ctl.pause()
    time.sleep(0.1)  # let the in-flight line finish so current_line settles
    current_line, _ = ctl.progress
    assert ctl.progress_point == ctl.toolpath.progress_position(current_line)
    ctl.resume()
    _pump_until(ctl, "done", answer="success")


def test_load_gcode_survives_a_bad_path_while_idle(config):
    ctl = _ctl(config)
    ctl.load_gcode("no_such_file.gcode")
    assert ctl.toolpath is None
    assert any(k == "log" and "no toolpath preview" in str(p) for k, p in ctl.poll_events())


def test_current_line_text_tracks_progress(config):
    ctl = _ctl(config, delay=0.03)
    assert ctl.current_line_text == ""
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.progress[0] > 0)
    ctl.pause()
    time.sleep(0.1)
    current_line, _ = ctl.progress
    assert ctl.current_line_text == ctl.gcode_lines[current_line - 1]
    ctl.resume()
    _pump_until(ctl, "done", answer="success")


# --- C21: Z-offset calibration ---------------------------------------

def test_start_z_calibration_homes_and_travels(config):
    # C27: start_z_calibration() also runs on a background thread (it starts
    # with a G28) - wait for it.
    ctl = _ctl(config)
    ctl.start_z_calibration()
    assert _wait(lambda: not ctl.busy)
    zc = config["zcal"]
    assert ctl.printer.sent[-2] == "G28"
    assert ctl.printer.sent[-1] == (
        f"G1 X{zc['x']:g} Y{zc['y']:g} Z{zc['start_z']:g} F{config['travel']['feed']:g}"
    )


def test_start_z_calibration_ignored_while_running(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    before = list(ctl.printer.sent)
    ctl.start_z_calibration()
    assert ctl.printer.sent == before
    _pump_until(ctl, "done", answer="success")


def test_nudge_z_sends_relative_move(config):
    ctl = _ctl(config)
    ctl.nudge_z(-0.05)
    zc = config["zcal"]
    assert ctl.printer.sent[-3:] == ["G91", f"G1 Z-0.05 F{zc['feed']:g}", "G90"]


def test_nudge_z_ignored_while_running(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    before = list(ctl.printer.sent)
    ctl.nudge_z(-0.05)
    assert ctl.printer.sent == before
    _pump_until(ctl, "done", answer="success")


def test_save_z_offset_writes_m851_and_persists(config, monkeypatch):
    # save_local_override writes to the real repo's config.local.yaml with no
    # path override (same pattern as the Settings dialog) - mock it here so
    # the test suite never touches that file, and assert on what would be
    # persisted instead.
    import magnet_embed.app as app_mod

    calls: list[dict] = []
    monkeypatch.setattr(app_mod, "save_local_override", lambda updates: calls.append(updates))

    ctl = _ctl(config)
    starting = ctl.config["zcal"]["probe_z_offset"]
    ctl.save_z_offset(-0.3)
    new_offset = round(starting - 0.3, 3)
    assert f"M851 Z{new_offset:g}" in ctl.printer.sent
    assert "M500" in ctl.printer.sent
    assert ctl.config["zcal"]["probe_z_offset"] == new_offset
    assert calls == [{"zcal": {"probe_z_offset": new_offset}}]


def test_save_z_offset_ignored_while_running(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    before = list(ctl.printer.sent)
    ctl.save_z_offset(-0.1)
    assert ctl.printer.sent == before
    _pump_until(ctl, "done", answer="success")


def test_z_calibration_surfaces_printer_error(config):
    ctl = _ctl(config)
    ctl.printer.command = _boom
    ctl.start_z_calibration()
    assert any(k == "error" for k, _ in ctl.poll_events())

    ctl2 = _ctl(config)
    ctl2.printer.command = _boom
    ctl2.nudge_z(-0.05)
    assert any(k == "error" for k, _ in ctl2.poll_events())

    ctl3 = _ctl(config)
    ctl3.printer.command = _boom
    ctl3.save_z_offset(-0.05)
    assert any(k == "error" for k, _ in ctl3.poll_events())


def test_progress_zero_then_advances_then_final(config):
    ctl = _ctl(config, delay=0.02)
    assert ctl.progress == (0, 0)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.progress[0] > 0)
    _pump_until(ctl, "done", answer="success")
    assert _wait(lambda: not ctl.running)
    done, total = ctl.progress
    assert total > 0 and done == total


# --- C25: emergency stop ----------------------------------------------

def test_emergency_stop_while_streaming_sends_m112_and_stops_the_run(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    assert _wait(lambda: ctl.running)
    ctl.emergency_stop()
    assert "M112" in ctl.printer.sent            # went out immediately, no idle guard
    assert ctl.estopped
    assert _wait(lambda: not ctl.running)        # run cancelled
    assert not ctl.runner.finished
    seen = ctl.poll_events()
    assert any(k == "error" and "EMERGENCY STOP" in str(p) for k, p in seen)


def test_emergency_stop_unblocks_a_pending_operator_prompt(config):
    ctl = _ctl(config, delay=0.03)
    ctl.load_gcode(SAMPLE)
    ctl.start_run()
    _pump_until(ctl, "prompt")                   # worker now blocked on the operator
    ctl.emergency_stop()
    assert _wait(lambda: not ctl.running)        # "abort" injected, worker exited
    assert "M112" in ctl.printer.sent


def test_emergency_stop_when_idle_still_sends_m112(config):
    ctl = _ctl(config)
    ctl.poll_events()
    ctl.emergency_stop()
    assert ctl.printer.sent[-1] == "M112"
    assert ctl.printer.query_state().nozzle_target == 0
    assert any(k == "error" and "M112" in str(p) for k, p in ctl.poll_events())


def test_emergency_stop_surfaces_a_send_failure(config):
    ctl = _ctl(config)
    ctl.poll_events()

    def dead(_line):
        from magnet_embed.exceptions import PrinterConnectionError

        raise PrinterConnectionError("port gone")

    ctl.printer.send_line = dead
    ctl.emergency_stop()                          # must not raise
    assert not ctl.estopped
    assert any(k == "error" and "power switch" in str(p) for k, p in ctl.poll_events())


def test_refresh_state_is_silent_after_an_estop(config):
    ctl = _ctl(config)
    ctl.emergency_stop()
    ctl.poll_events()
    before = list(ctl.printer.sent)
    ctl.refresh_state()                          # the panel polls this every 2 s
    assert ctl.printer.sent == before            # nothing sent to a halted board
    assert ctl.poll_events() == []               # and no error spam


def test_reconnect_clears_estopped(config):
    ctl = _ctl(config)
    ctl.emergency_stop()
    assert ctl.estopped
    ctl.printer.command("M999")
    ctl.connect()
    assert not ctl.estopped


# --- C22: link_summary (GUI mode/port label) --------------------------

def test_link_summary_simulator(config):
    ctl = _ctl(config)
    assert ctl.link_summary == "simulator"


class _FakePort:
    def __init__(self, port):
        self.port = port


def test_link_summary_real_printer_only(config):
    ctl = Controller(_FakePort("COM3"), None, config)
    assert ctl.link_summary == "printer COM3"


def test_link_summary_real_printer_and_dispenser(config):
    ctl = Controller(_FakePort("COM3"), _FakePort("COM4"), config)
    assert ctl.link_summary == "printer COM3 + dispenser COM4"


def test_link_summary_real_printer_sim_dispenser(config):
    ctl = Controller(_FakePort("COM3"), SimDispenser(), config)
    assert ctl.link_summary == "printer COM3 + dispenser (sim)"
