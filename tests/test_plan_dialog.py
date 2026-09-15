"""`magnet_embed.ui.plan_dialog` — pure helpers for placing + saving the sentinel (C17)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from magnet_embed.gcode.sentinel import parse_sentinel
from magnet_embed.gcode.toolpath import parse_toolpath
from magnet_embed.state import MagnetInsert
from magnet_embed.ui.plan_dialog import (
    envelope_report,
    magnet_output_path,
    resolve_target_z,
    save_magnet_gcode,
)

DATA = Path(__file__).parent / "data"


@pytest.fixture
def cfg(config):
    return {**config, "magnet_tool_offset": {"x": 20.0, "y": 0.0, "z": 2.0}}


def MI(**kw):
    base = dict(pocket_x=110.0, pocket_y=100.0, seat_z=6.0, shear_dir="+X")
    base.update(kw)
    return MagnetInsert(**base)


def test_resolve_target_z_layer_mode():
    tp = parse_toolpath(DATA / "cura_sample.gcode")   # layer_z = [0.2, 2, 4, 6, 8]
    assert resolve_target_z("layer", 2, tp) == 4.0
    assert resolve_target_z("layer", 99, tp) == 8.0   # clamp
    assert resolve_target_z("z", 5.5, tp) == 5.5


def test_magnet_output_path():
    assert magnet_output_path("a/b/part.gcode").name == "part.magnet.gcode"


def test_save_writes_a_parseable_sentinel(tmp_path):
    src = tmp_path / "part.gcode"
    shutil.copy(DATA / "cura_sample.gcode", src)
    out = save_magnet_gcode(src, MI(), target_z=4.0)
    assert out == tmp_path / "part.magnet.gcode"

    hits = [parse_sentinel(ln) for ln in out.read_text().splitlines()]
    mi = next(h for h in hits if h is not None)
    assert (mi.pocket_x, mi.pocket_y, mi.seat_z, mi.shear_dir) == (110.0, 100.0, 6.0, "+X")


def test_save_with_pause_prepends_m0(tmp_path):
    src = tmp_path / "part.gcode"
    shutil.copy(DATA / "cura_sample.gcode", src)
    out = save_magnet_gcode(src, MI(), target_z=4.0, emit_pause=True)
    lines = out.read_text().splitlines()
    si = next(i for i, ln in enumerate(lines) if ln.startswith(";MAGNET_INSERT"))
    assert lines[si - 1].strip().startswith("M0")


def test_envelope_report_flags_a_pocket_off_the_bed(cfg):
    tp = parse_toolpath(DATA / "cura_sample.gcode")
    bad = envelope_report(MI(pocket_x=5.0, shear_dir="-X"), cfg, tp)
    assert any("approach X" in b for b in bad)


def test_envelope_report_clean_for_a_central_pocket(cfg):
    tp = parse_toolpath(DATA / "cura_sample.gcode")
    assert envelope_report(MI(), cfg, tp) == []


def test_envelope_report_flags_nozzle_into_the_part(cfg):
    """C25: the dialog runs the same collision guard as the run. The cura
    coupon spans X 0..50; a pocket at X30 with a +20 mm offset puts the nozzle
    at X10, inside the part, pressing to Z 4 below the printed top."""
    tp = parse_toolpath(DATA / "cura_sample.gcode")
    bad = envelope_report(MI(pocket_x=30.0, pocket_y=30.0), cfg, tp)
    assert any("printed part" in b for b in bad)
