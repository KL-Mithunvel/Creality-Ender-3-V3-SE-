"""`magnet_embed.gcode.toolpath` — parse a slice into a drawable model (C14)."""

from __future__ import annotations

from pathlib import Path

import pytest

from magnet_embed.gcode.toolpath import parse_toolpath

DATA = Path(__file__).parent / "data"


def test_sample_layers_from_markers():
    tp = parse_toolpath(DATA / "sample.gcode")
    assert tp.layer_z == [0.2, 2.0, 4.0, 6.0, 8.0]
    assert tp.layer_count == 5


def test_cura_sample_layers():
    tp = parse_toolpath(DATA / "cura_sample.gcode")
    assert tp.layer_z == [0.2, 2.0, 4.0, 6.0, 8.0]


def test_prusa_sample_layers_from_z_comments():
    # the PrusaSlicer fixture has ;Z: comments but no Z moves at all
    tp = parse_toolpath(DATA / "prusa_sample.gcode")
    assert tp.layer_z == [0.2, 2.0, 4.0, 6.0]
    assert tp.layer_count == 4


def test_segments_split_travel_and_extrude():
    tp = parse_toolpath(DATA / "cura_sample.gcode")
    assert any(s.extruding for s in tp.segments)
    assert any(not s.extruding for s in tp.segments)
    assert all(s.length > 0 for s in tp.segments if s.extruding)


def test_bbox_covers_the_printed_extent():
    tp = parse_toolpath(DATA / "cura_sample.gcode")
    assert tp.bbox_max[0] >= 50 and tp.bbox_max[1] >= 50
    assert tp.bbox_max[2] == pytest.approx(8.0)
    assert tp.top_z == pytest.approx(8.0)


def test_layer_for_z():
    tp = parse_toolpath(DATA / "sample.gcode")
    assert tp.layer_for_z(6.0) == 3
    assert tp.layer_for_z(3.5) == 2       # first layer >= 3.5 is 4.0 -> index 2
    assert tp.layer_for_z(99) == 4        # clamp to the top layer


def test_distances_and_time_positive():
    tp = parse_toolpath(DATA / "cura_sample.gcode")
    assert tp.extrude_distance() > 0
    assert tp.travel_distance() >= 0
    assert tp.est_time_s() > 0


def test_unmarked_file_is_layered_by_z(tmp_path):
    p = tmp_path / "raw.gcode"
    p.write_text(
        "G90\nM82\n"
        "G1 Z0.2 F1200\nG1 X0 Y0 E0\nG1 X10 Y0 E1\n"
        "G1 Z0.4\nG1 X10 Y10 E2\n"
        "G1 Z0.6\nG1 X0 Y10 E3\n",
        encoding="utf-8",
    )
    tp = parse_toolpath(p)
    assert tp.layer_z == [0.2, 0.4, 0.6]


def test_relative_moves_and_g92(tmp_path):
    p = tmp_path / "rel.gcode"
    p.write_text(
        "G90\nM83\nG1 Z0.2\nG1 X10 Y0 E1\n"
        "G91\nG1 X5 Y0 E1\n"           # relative: ends at X15
        "G90\nG92 E0\nG1 X15 Y10 E1\n",
        encoding="utf-8",
    )
    tp = parse_toolpath(p)
    last = tp.segments[-1]
    assert last.p1[0] == pytest.approx(15.0)
    assert last.p1[1] == pytest.approx(10.0)
