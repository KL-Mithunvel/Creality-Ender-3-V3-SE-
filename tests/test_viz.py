"""`magnet_embed.viz.toolpath_fig` — preview geometry + headless drawing (C16)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from matplotlib.figure import Figure

from magnet_embed.gcode.toolpath import parse_toolpath
from magnet_embed.sequences.geometry import plan_insert_moves
from magnet_embed.state import MagnetInsert, PrinterState
from magnet_embed.viz import toolpath_fig as tf

DATA = Path(__file__).parent / "data"


@pytest.fixture
def cfg(config):
    return {**config, "magnet_tool_offset": {"x": 20.0, "y": 0.0, "z": 2.0}}


def MI(**kw):
    base = dict(pocket_x=110.0, pocket_y=100.0, seat_z=6.0, shear_dir="+X")
    base.update(kw)
    return MagnetInsert(**base)


def _saved():
    return PrinterState(x=100.0, y=100.0, z=5.0)


def test_nozzle_waypoints_start_at_saved(cfg):
    mv = plan_insert_moves(MI(), cfg, _saved())
    wp = tf.nozzle_waypoints(mv, _saved())
    assert wp[0] == (100.0, 100.0, 5.0)
    assert len(wp) == len(mv) + 1


def test_pole_waypoints_apply_the_offset(cfg):
    mv = plan_insert_moves(MI(), cfg, _saved())
    pol = tf.pole_waypoints(mv, _saved(), cfg)
    assert pol[0] == (120.0, 100.0, 7.0)   # saved + (20, 0, 2)


def test_sample_polyline_endpoints_and_midpoint():
    pts = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)]
    assert tf.sample_polyline(pts, 0.0)[0] == (0.0, 0.0, 0.0)
    assert tf.sample_polyline(pts, 1.0)[0] == (10.0, 10.0, 0.0)
    mid, seg = tf.sample_polyline(pts, 0.5)
    assert mid == pytest.approx((10.0, 0.0, 0.0))
    assert seg in (0, 1)


def test_state_at_z_picks_last_move_at_or_below():
    tp = parse_toolpath(DATA / "sample.gcode")
    assert tf.state_at_z(tp, 4.0).z <= 4.0 + 1e-6
    assert tf.state_at_z(tp, 99.0).z == pytest.approx(8.0)


def test_draw_functions_run_headless(cfg):
    tp = parse_toolpath(DATA / "sample.gcode")
    fig = Figure()
    ax = fig.add_subplot(1, 2, 1)
    tf.draw_layer_xy(ax, tp, 2)
    ax2 = fig.add_subplot(1, 2, 2)
    tf.draw_side_xz(ax2, tp)

    mv = plan_insert_moves(MI(), cfg, _saved())
    art = tf.draw_insert_overlay(ax, mv, _saved(), cfg, plane="xy")
    seg = tf.update_insert_marker(art, 0.5, "xy")
    assert 0 <= seg < len(mv)

    ax3 = Figure().add_subplot(1, 1, 1, projection="3d")
    tf.draw_path_3d(ax3, tp)


def test_preview_module_imports():
    import magnet_embed.viz.preview  # noqa: F401


def test_draw_live_layer_and_update_marker():
    tp = parse_toolpath(DATA / "sample.gcode")
    fig = Figure()
    ax = fig.add_subplot(1, 1, 1)
    art = tf.draw_live_layer(ax, tp, 2)
    assert "marker" in art
    assert len(art["marker"].get_xdata()) == 0   # empty until the first update

    pt = tp.progress_position(tp.segments[-1].line_no)
    tf.update_live_marker(art, pt)
    assert list(art["marker"].get_xdata()) == [pt[0]]
    assert list(art["marker"].get_ydata()) == [pt[1]]


def test_draw_live_3d_and_update():
    tp = parse_toolpath(DATA / "sample.gcode")
    fig = Figure()
    ax = fig.add_subplot(1, 1, 1, projection="3d")
    art = tf.draw_live_3d(ax, tp, (220.0, 220.0))
    assert "marker" in art and "path" in art
    assert len(art["marker"].get_data_3d()[0]) == 0
    assert len(art["path"].get_data_3d()[0]) == 0
    # equal mm-per-axis box aspect, covering both the part and the bed plate
    assert ax.get_box_aspect() is not None

    last_line = tp.segments[-1].line_no
    pt = tp.progress_position(last_line)
    tf.update_live_3d(art, tp, last_line)
    xs, ys, zs = art["marker"].get_data_3d()
    assert list(xs) == [pt[0]]
    assert list(ys) == [pt[1]]
    assert list(zs) == [pt[2]]
    assert len(art["path"].get_data_3d()[0]) > 0  # the printed-so-far path grew


def test_draw_live_3d_local_mode_crops_tight_to_the_part():
    tp = parse_toolpath(DATA / "sample.gcode")
    fig = Figure()

    ax_global = fig.add_subplot(1, 2, 1, projection="3d")
    tf.draw_live_3d(ax_global, tp, (220.0, 220.0), show_bed=True)
    gx0, gx1 = ax_global.get_xlim3d()
    assert gx1 - gx0 == pytest.approx(220.0)  # spans the whole bed
    assert len(ax_global.lines) == 3  # bed outline + empty path + empty marker

    ax_local = fig.add_subplot(1, 2, 2, projection="3d")
    tf.draw_live_3d(ax_local, tp, (220.0, 220.0), show_bed=False)
    lx0, lx1 = ax_local.get_xlim3d()
    assert lx1 - lx0 < gx1 - gx0  # tighter than the full bed
    assert len(ax_local.lines) == 2  # no bed outline in Local mode, just path + marker


def test_progressive_path_3d_only_includes_printed_extruding_moves():
    tp = parse_toolpath(DATA / "sample.gcode")
    first_extrude = next(s for s in tp.segments if s.extruding)

    xs, ys, zs = tf.progressive_path_3d(tp, first_extrude.line_no - 1)
    assert xs == [] and ys == [] and zs == []  # nothing printed yet

    xs, ys, zs = tf.progressive_path_3d(tp, first_extrude.line_no)
    assert xs[-1] == first_extrude.p1[0]
    assert ys[-1] == first_extrude.p1[1]
    assert zs[-1] == first_extrude.p1[2]

    last_line = tp.segments[-1].line_no
    xs_full, ys_full, zs_full = tf.progressive_path_3d(tp, last_line)
    assert len(xs_full) >= len(xs)
    assert xs_full[-1] == tp.segments[-1].p1[0] or math.isnan(xs_full[-1])
