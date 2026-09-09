import pytest

from magnet_embed.exceptions import SentinelParseError
from magnet_embed.gcode.sentinel import parse_sentinel
from magnet_embed.state import MagnetInsert


def test_parse_valid():
    mi = parse_sentinel(";MAGNET_INSERT X30.0 Y30.0 Z0.8 S+X")
    assert isinstance(mi, MagnetInsert)
    assert mi.pocket_xy == (30.0, 30.0)
    assert mi.seat_z == 0.8
    assert mi.shear_dir == "+X"
    assert mi.raw == ";MAGNET_INSERT X30.0 Y30.0 Z0.8 S+X"


def test_parse_tolerates_whitespace_and_negatives():
    mi = parse_sentinel("   ;MAGNET_INSERT X-1.5 Y2 Z10 S-Y  ")
    assert mi.pocket_xy == (-1.5, 2.0)
    assert mi.seat_z == 10.0
    assert mi.shear_dir == "-Y"


@pytest.mark.parametrize("line", [";LAYER:3", "G1 X10 Y10", "", "; MAGNET stuff", ";MAGNET_INSERTED X1 Y1 Z1 S+X"])
def test_non_sentinel_returns_none(line):
    assert parse_sentinel(line) is None


@pytest.mark.parametrize(
    "line",
    [
        ";MAGNET_INSERT X30 Y30 S+X",        # no Z
        ";MAGNET_INSERT Y30 Z1 S+X",         # no X
        ";MAGNET_INSERT X30 Y30 Z1",         # no S
        ";MAGNET_INSERT X30 Y30 Z1 S+Q",     # bad direction letter
        ";MAGNET_INSERT X30 Y30 Z1 SX",      # missing sign
    ],
)
def test_malformed_sentinel_raises(line):
    with pytest.raises(SentinelParseError):
        parse_sentinel(line)


def test_custom_token():
    assert parse_sentinel(";FOO X1 Y2 Z3 S+X", token=";FOO").shear_dir == "+X"
    assert parse_sentinel(";MAGNET_INSERT X1 Y2 Z3 S+X", token=";FOO") is None
