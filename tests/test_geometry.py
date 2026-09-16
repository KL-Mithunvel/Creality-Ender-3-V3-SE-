"""`magnet_embed.sequences.geometry` — shared insert-motion targets (C15)."""

from __future__ import annotations

import pytest

from magnet_embed.gcode.toolpath import Segment, Toolpath
from magnet_embed.sequences.geometry import (
    check_envelope,
    compute_targets,
    part_footprint,
    plan_insert_moves,
    pole_point,
)
from magnet_embed.state import MagnetInsert, PrinterState

OFFSET = {"x": 20.0, "y": 0.0, "z": 2.0}


@pytest.fixture
def cfg(config):
    return {**config, "magnet_tool_offset": OFFSET}


def _saved(x=100.0, y=100.0, z=5.0):
    return PrinterState(x=x, y=y, z=z, e=42.0, nozzle_target=210)


def MI(**kw):
    base = dict(pocket_x=110.0, pocket_y=100.0, seat_z=6.0, shear_dir="+X")
    base.update(kw)
    return MagnetInsert(**base)


def test_targets_apply_the_offset(cfg):
    t = compute_targets(MI(), cfg, _saved())
    assert t.approach_xy == (90.0, 100.0)      # 110-20, 100-0
    assert t.press_z == 4.0                    # 6 - 2
    assert t.shear_xy == (95.0, 100.0)         # +X by shear.distance 5
    assert t.safe_z == 20.0                    # 5 + safe_z_lift 15


def test_plan_matches_the_asserted_insert_targets(cfg):
    moves = plan_insert_moves(MI(), cfg, _saved())
    by = {(m.phase, m.kind): m.endpoint for m in moves}
    assert by[("APPROACH", "travel")] == (90.0, 100.0, 20.0)
    assert by[("PRESS", "press")] == (90.0, 100.0, 4.0)
    assert by[("SHEAR", "shear")] == (95.0, 100.0, 4.0)
    assert moves[-1].endpoint == (100.0, 100.0, 5.0)   # RESUME back to saved Z


def test_plan_phase_order(cfg):
    phases = [m.phase for m in plan_insert_moves(MI(), cfg, _saved())]
    assert phases == [
        "PARK", "APPROACH", "PRESS", "SHEAR", "LIFT", "CLEAR", "RESUME", "RESUME"
    ]


def test_pole_tip_lands_on_the_seat(cfg):
    t = compute_targets(MI(), cfg, _saved())
    nozzle_at_press = (*t.approach_xy, t.press_z)
    assert pole_point(nozzle_at_press, cfg) == (110.0, 100.0, 6.0)   # pocket XY + seat Z


def test_envelope_ok_for_a_central_pocket(cfg):
    assert check_envelope(MI(), cfg, _saved()) == []


def test_envelope_flags_a_pocket_off_the_bed(cfg):
    bad = check_envelope(MI(pocket_x=5.0, shear_dir="-X"), cfg, _saved())
    assert any("approach X" in b for b in bad)


def test_envelope_flags_negative_press_z(cfg):
    bad = check_envelope(MI(seat_z=1.0), cfg, _saved())   # 1 - offset.z 2 = -1
    assert any("press Z" in b for b in bad)
    assert any("build plate" in b for b in bad)            # C25: says what would be hit


# --- C25: damage guard ------------------------------------------------

def _part(x0, y0, x1, y1, top):
    """A toolpath stand-in: the guard only needs the printed bounding box."""
    return Toolpath(segments=[], layer_z=[top], bbox_min=(x0, y0, 0.2), bbox_max=(x1, y1, top))


def test_envelope_flags_a_pocket_off_the_bed_even_if_the_nozzle_is_on_it(cfg):
    # pole 20 mm +X of the nozzle: pocket at X230 puts the nozzle at X210 (legal)
    bad = check_envelope(MI(pocket_x=230.0), cfg, _saved())
    assert any("pocket X" in b and "outside the bed" in b for b in bad)


def test_envelope_flags_nozzle_into_the_printed_part(cfg):
    # part spans X 50..150; pocket at X110 -> nozzle at X90, inside; press Z 4 < top 5 + 1
    part = _part(50, 50, 150, 150, top=5.0)
    bad = check_envelope(MI(), cfg, _saved(z=5.0), part)
    assert len(bad) == 1
    assert "printed part" in bad[0] and "PRESS" in bad[0]


def test_envelope_ok_when_the_nozzle_lands_outside_the_footprint(cfg):
    # part spans X 100..150 (+2 mm margin -> 98..152); nozzle at X90 and shear to X95 stay clear
    part = _part(100, 50, 150, 150, top=5.0)
    assert check_envelope(MI(), cfg, _saved(z=5.0), part) == []


def test_envelope_flags_a_shear_that_crosses_into_the_part(cfg):
    # nozzle presses at X90 just outside a part starting at X93 (margin 2 -> 91),
    # then shears +X by 5 mm -> ends at X95, inside
    part = _part(93, 50, 150, 150, top=5.0)
    bad = check_envelope(MI(), cfg, _saved(z=5.0), part)
    assert len(bad) == 1 and "SHEAR" in bad[0]


def test_envelope_ok_when_the_nozzle_stays_above_the_part(cfg):
    # pole 2 mm BELOW the nozzle: press Z = 6 + 2 = 8 >= printed top 5 + clearance 1
    low_pole = {**cfg, "magnet_tool_offset": {**OFFSET, "z": -2.0}}
    part = _part(50, 50, 150, 150, top=5.0)
    assert check_envelope(MI(), low_pole, _saved(z=5.0), part) == []


def test_envelope_clearance_is_configurable(cfg):
    # press Z 4 vs top 3: clear with 0.5 mm clearance, not with 1.5 mm
    part = _part(50, 50, 150, 150, top=3.0)
    ok = {**cfg, "collision": {"nozzle_clearance_mm": 0.5, "footprint_margin_mm": 0.0}}
    assert check_envelope(MI(), ok, _saved(z=3.0), part) == []
    tight = {**cfg, "collision": {"nozzle_clearance_mm": 1.5, "footprint_margin_mm": 0.0}}
    assert check_envelope(MI(), tight, _saved(z=3.0), part) != []


def test_envelope_without_a_toolpath_only_checks_bed_limits(cfg):
    assert check_envelope(MI(), cfg, _saved(z=5.0), None) == []


def test_part_footprint_grows_by_the_margin():
    part = _part(10, 20, 30, 40, top=5.0)
    assert part_footprint(part, 2.0) == (8.0, 18.0, 32.0, 42.0)


# --- C30: restrict the collision footprint to already-printed layers -----

def _layered_part(layers):
    """`layers`: `[(z, x0, y0, x1, y1), ...]`, one box per ascending layer
    index. Two extruding segments per layer are enough to fix its bbox."""
    segments = []
    for idx, (z, x0, y0, x1, y1) in enumerate(layers):
        n = idx * 2
        segments.append(Segment((x0, y0, z), (x1, y0, z), True, idx, 1500.0, n + 1))
        segments.append(Segment((x1, y0, z), (x1, y1, z), True, idx, 1500.0, n + 2))
    layer_z = [z for z, *_ in layers]
    xs = [x for _, x0, _, x1, _ in layers for x in (x0, x1)]
    ys = [y for _, _, y0, _, y1 in layers for y in (y0, y1)]
    return Toolpath(
        segments=segments, layer_z=layer_z,
        bbox_min=(min(xs), min(ys), layer_z[0]),
        bbox_max=(max(xs), max(ys), layer_z[-1]),
    )


def test_envelope_ignores_a_wider_not_yet_printed_upper_layer(cfg):
    """C30: the whole-file bbox (layer 1, unprinted, spans X 50..250) would
    flag this pocket; restricted to what's actually printed at the sentinel
    (layer 0, X 200..250, nowhere near the nozzle), it's accepted."""
    part = _layered_part([
        (5.0, 200.0, 50.0, 250.0, 150.0),   # layer 0 - printed by saved.z=5.0
        (10.0, 50.0, 50.0, 250.0, 150.0),   # layer 1 - not printed yet, much wider
    ])
    # sanity: the old whole-file box does span the nozzle's X - proves the
    # narrower box is doing the work, not that the part just never collided
    assert part_footprint(part, 2.0)[0] < 90.0
    assert check_envelope(MI(), cfg, _saved(z=5.0), part) == []


def test_envelope_still_flags_a_collision_in_an_already_printed_layer(cfg):
    """Unchanged from today: material in the layer that's actually printed
    still refuses the insert, regardless of what's above it."""
    part = _layered_part([
        (5.0, 50.0, 50.0, 150.0, 150.0),    # layer 0 - printed, spans the nozzle's X
        (10.0, 200.0, 200.0, 300.0, 300.0),  # layer 1 - not printed yet, irrelevant
    ])
    bad = check_envelope(MI(), cfg, _saved(z=5.0), part)
    assert len(bad) == 1 and "printed part" in bad[0]
