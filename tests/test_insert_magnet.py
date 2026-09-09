import pytest

from magnet_embed.exceptions import DispenserError, OutOfEnvelopeError, SequenceAborted
from magnet_embed.links.dispenser_sim import SimDispenser
from magnet_embed.links.printer_sim import SimPrinter
from magnet_embed.sequences.insert_magnet import insert_magnet
from magnet_embed.state import MagnetInsert

# offset = pole - nozzle: pole is 20 mm +X of the nozzle and 2 mm above its tip.
OFFSET = {"x": 20.0, "y": 0.0, "z": 2.0}


@pytest.fixture
def cfg(config):
    return {**config, "magnet_tool_offset": OFFSET}


@pytest.fixture
def printer():
    p = SimPrinter()
    p.connect()
    p.command("G90")
    p.command("M82")
    p.command("M104 S210")
    p.command("M140 S60")
    p.command("G1 X100 Y100 Z5 E42 F1800")  # mid-print
    return p


@pytest.fixture
def dispenser():
    d = SimDispenser()
    d.connect()
    return d


def MI(**kw):
    base = dict(pocket_x=110.0, pocket_y=100.0, seat_z=6.0, shear_dir="+X")
    base.update(kw)
    return MagnetInsert(**base)


def _xyz(printer):
    return [(round(x, 3), round(y, 3), round(z, 3)) for x, y, z, _ in printer.moves]


def always(answer):
    return lambda stage: answer


def test_happy_path_restores_position_modes_and_temp(printer, dispenser, cfg):
    insert_magnet(printer, dispenser, MI(), cfg, always("success"))

    st = printer.query_state()
    assert (round(st.x, 3), round(st.y, 3), round(st.z, 3)) == (100.0, 100.0, 5.0)
    assert st.e == 42.0                      # G92 restored the extruder reference
    assert st.nozzle_target == 210
    assert st.nozzle_temp == 210             # M109 reheated
    assert st.absolute_xyz is True and st.absolute_e is True
    assert dispenser.count == 1


def test_moves_use_the_tool_offset(printer, dispenser, cfg):
    insert_magnet(printer, dispenser, MI(), cfg, always("success"))
    moves = _xyz(printer)
    safe_z = 5.0 + cfg["park"]["safe_z_lift_mm"]          # 20
    assert (90.0, 100.0, safe_z) in moves                 # APPROACH: 110-20, 100-0
    assert (90.0, 100.0, 4.0) in moves                    # PRESS: seat_z 6 - offset.z 2
    assert (95.0, 100.0, 4.0) in moves                    # SHEAR: +X by shear.distance 5


def test_never_homes(printer, dispenser, cfg):
    insert_magnet(printer, dispenser, MI(), cfg, always("success"))
    assert not any(s.strip().upper().startswith("G28") for s in printer.sent)


def test_out_of_envelope_aborts_before_moving(printer, dispenser, cfg):
    before = printer.query_state()
    with pytest.raises(OutOfEnvelopeError):
        insert_magnet(printer, dispenser, MI(pocket_x=5.0, shear_dir="-X"), cfg, always("success"))
    after = printer.query_state()
    assert (after.x, after.y, after.z) == (before.x, before.y, before.z)
    assert dispenser.count == 0


def test_abort_at_confirm_turns_nozzle_off(printer, dispenser, cfg):
    with pytest.raises(SequenceAborted):
        insert_magnet(printer, dispenser, MI(), cfg, always("abort"))
    assert printer.query_state().nozzle_target == 0


def test_retry_redispenses_then_resumes(printer, dispenser, cfg):
    answers = iter(["retry", "retry", "success"])
    insert_magnet(printer, dispenser, MI(), cfg, lambda stage: next(answers))
    assert dispenser.count == 3
    assert dispenser.last == "dispense"
    assert printer.query_state().nozzle_target == 210


def test_retry_limit_aborts(printer, dispenser, cfg):
    with pytest.raises(SequenceAborted):
        insert_magnet(printer, dispenser, MI(), cfg, always("retry"))
    assert printer.query_state().nozzle_target == 0


def test_dispenser_failure_keeps_printer_resumable(printer, cfg):
    bad = SimDispenser(fail_on_dispense=True)
    bad.connect()
    with pytest.raises(DispenserError):
        insert_magnet(printer, bad, MI(), cfg, always("success"))
    # nozzle target put back to the saved value, not left at standby
    assert printer.query_state().nozzle_target == 210


def test_manual_dispense_prompt_when_no_dispenser(printer, cfg):
    seen = []

    def prompt(stage):
        seen.append(stage)
        return "ready" if stage == "dispense" else "success"

    insert_magnet(printer, None, MI(), cfg, prompt)
    assert "dispense" in seen and "confirm" in seen


def test_manual_dispense_abort(printer, cfg):
    with pytest.raises(SequenceAborted):
        insert_magnet(printer, None, MI(), cfg, always("abort"))


def test_resume_restores_relative_modes(printer, dispenser, cfg):
    printer.command("M83")
    printer.command("G91")
    insert_magnet(printer, dispenser, MI(), cfg, always("success"))
    st = printer.query_state()
    assert st.absolute_e is False
    assert st.absolute_xyz is False
