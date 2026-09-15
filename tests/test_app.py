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
    assert any(k == "log" and "run is active" in str(p) for k, p in ctl.poll_events())
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
    ctl = _ctl(config)
    ctl.level_bed()
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
