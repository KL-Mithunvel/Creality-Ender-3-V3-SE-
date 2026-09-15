"""`magnet_embed.viz.toolpath_fig` — preview geometry + headless drawing (C16)."""

from __future__ import annotations

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


def test_draw_live_3d_and_update_marker():
    tp = parse_toolpath(DATA / "sample.gcode")
    fig = Figure()
    ax = fig.add_subplot(1, 1, 1, projection="3d")
    art = tf.draw_live_3d(ax, tp)
    assert "marker" in art
    assert len(art["marker"].get_data_3d()[0]) == 0

    pt = tp.progress_position(tp.segments[-1].line_no)
    tf.update_live_marker_3d(art, pt)
    xs, ys, zs = art["marker"].get_data_3d()
    assert list(xs) == [pt[0]]
    assert list(ys) == [pt[1]]
    assert list(zs) == [pt[2]]
