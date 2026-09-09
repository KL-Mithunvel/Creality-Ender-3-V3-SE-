"""`magnet_embed.sequences.geometry` — shared insert-motion targets (C15)."""

from __future__ import annotations

import pytest

from magnet_embed.sequences.geometry import (
    check_envelope,
    compute_targets,
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
