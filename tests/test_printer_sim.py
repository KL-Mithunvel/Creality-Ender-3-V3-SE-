import pytest

from magnet_embed.exceptions import PrinterConnectionError
from magnet_embed.links.printer_sim import SimPrinter


@pytest.fixture
def printer():
    p = SimPrinter()
    p.connect()
    return p


def test_send_before_connect_raises():
    with pytest.raises(PrinterConnectionError):
        SimPrinter().send_line("G28")


def test_absolute_move_tracks_position_and_feed(printer):
    printer.command("G90")
    printer.command("G1 X10 Y20 Z0.4 F1500")
    st = printer.query_state()
    assert (st.x, st.y, st.z) == (10.0, 20.0, 0.4)
    assert st.feedrate == 1500.0


def test_relative_move(printer):
    printer.command("G90")
    printer.command("G1 X10 Y10")
    printer.command("G91")
    printer.command("G1 X5 Y-3 Z1")
    st = printer.query_state()
    assert (st.x, st.y, st.z) == (15.0, 7.0, 1.0)


def test_m112_halts_until_m999(printer):
    from magnet_embed.exceptions import PrinterError

    printer.command("M104 S200")
    printer.command("M140 S60")
    printer.command("M112")
    st = printer.query_state()
    assert printer.halted
    assert st.nozzle_target == 0 and st.bed_target == 0     # heaters killed
    with pytest.raises(PrinterError):
        printer.command("G1 X10")                           # dead until reset
    printer.command("M999")
    assert not printer.halted
    printer.command("G1 X10")                               # alive again


def test_relative_extrusion(printer):
    printer.command("M83")
    printer.command("G1 E1")
    printer.command("G1 E1.5")
    assert printer.query_state().e == 2.5


def test_absolute_extrusion(printer):
    printer.command("M82")
    printer.command("G1 E5")
    printer.command("G1 E7")
    assert printer.query_state().e == 7.0


def test_temperature_set(printer):
    printer.command("M104 S200")
    printer.command("M140 S60")
    st = printer.query_state()
    assert st.nozzle_target == 200 and st.nozzle_temp == 200
    assert st.bed_target == 60 and st.bed_temp == 60


def test_g92_resets_position(printer):
    printer.command("G90")
    printer.command("G1 X50 E9")
    printer.command("G92 X0 E0")
    st = printer.query_state()
    assert st.x == 0.0 and st.e == 0.0


def test_g28_homes_all_and_selective(printer):
    printer.command("G90")
    printer.command("G1 X50 Y50 Z10")
    printer.command("G28 X")
    st = printer.query_state()
    assert (st.x, st.y, st.z) == (0.0, 50.0, 10.0)
    printer.command("G28")
    st = printer.query_state()
    assert (st.x, st.y, st.z) == (0.0, 0.0, 0.0)
    assert st.homed


def test_ok_payload_and_unknown_lines(printer):
    assert printer.command("M117 hello world").startswith("ok")
    assert printer.command(";LAYER:5").startswith("ok")
    assert printer.command("").startswith("ok")


def test_move_log(printer):
    printer.command("G90")
    printer.command("G1 X1 Y1")
    printer.command("G1 X2 Y2")
    assert printer.moves[-2:] == [(1.0, 1.0, 0.0, 0.0), (2.0, 2.0, 0.0, 0.0)]
