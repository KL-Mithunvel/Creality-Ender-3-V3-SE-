"""Geometry helpers + matplotlib drawing for the toolpath / insert preview.

Split from `preview.py` so the pure helpers (`nozzle_waypoints`, `pole_waypoints`,
`sample_polyline`, `state_at_z`) are unit-testable with no display. The `draw_*`
functions take a matplotlib `Axes` and never create a figure or touch a GUI backend.
"""

from __future__ import annotations

import math

import numpy as np

from ..gcode.toolpath import Toolpath
from ..sequences.geometry import InsertMove, plan_insert_moves, pole_point
from ..state import MagnetInsert, PrinterState

Point = tuple[float, float, float]

PHASE_COLOR: dict[str, str] = {
    "PARK": "#1f8a82",
    "APPROACH": "#d79a2b",
    "PRESS": "#d9662f",
    "SHEAR": "#c53b3b",
    "LIFT": "#3f79c8",
    "CLEAR": "#6b7280",
    "RESUME": "#7a58c8",
}
_EXTRUDE = "#c79a63"
_TRAVEL = "#cfd2cb"
_SILHOUETTE = "#e2e0d8"


# --- pure helpers ---------------------------------------------------------

def nozzle_waypoints(moves: list[InsertMove], saved: PrinterState) -> list[Point]:
    """Start position + one point per move endpoint (nozzle tip)."""
    return [(saved.x, saved.y, saved.z), *(m.endpoint for m in moves)]


def pole_waypoints(
    moves: list[InsertMove], saved: PrinterState, config: dict
) -> list[Point]:
    return [pole_point(p, config) for p in nozzle_waypoints(moves, saved)]


def phase_labels(moves: list[InsertMove]) -> list[str]:
    """Phase active on each waypoint segment (len == len(waypoints) - 1)."""
    return [m.phase for m in moves]


def sample_polyline(pts: list[Point], t: float) -> tuple[Point, int]:
    """Point at fraction `t` (0..1) along the polyline, and the segment index."""
    if not pts:
        return (0.0, 0.0, 0.0), 0
    if len(pts) == 1:
        return pts[0], 0
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg) or 1.0
    target = max(0.0, min(1.0, t)) * total
    acc = 0.0
    for i, d in enumerate(seg):
        if acc + d >= target or i == len(seg) - 1:
            u = 0.0 if d == 0 else (target - acc) / d
            a, b = pts[i], pts[i + 1]
            return (
                a[0] + (b[0] - a[0]) * u,
                a[1] + (b[1] - a[1]) * u,
                a[2] + (b[2] - a[2]) * u,
            ), i
        acc += d
    return pts[-1], len(seg) - 1


def state_at_z(tp: Toolpath, z: float) -> PrinterState:
    """Approximate the saved printer state when the print reaches height `z`:
    the endpoint of the last extruding move at or below `z`."""
    x = y = 0.0
    zz = tp.layer_z[0] if tp.layer_z else 0.0
    for s in tp.segments:
        if s.extruding and s.p1[2] <= z + 1e-4:
            x, y, zz = s.p1
    return PrinterState(x=x, y=y, z=zz)


# --- drawing ------------------------------------------------------------

def draw_layer_xy(ax, tp: Toolpath, layer: int) -> None:
    ax.clear()
    for s in tp.segments_in_layer(layer):
        ax.plot(
            [s.p0[0], s.p1[0]], [s.p0[1], s.p1[1]],
            color=_EXTRUDE if s.extruding else _TRAVEL,
            lw=1.5 if s.extruding else 0.6,
            zorder=3 if s.extruding else 1,
        )
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_title(
        f"layer {layer} / {tp.layer_count - 1}   Z {tp.layer_z[layer]:.2f} mm",
        fontsize=9,
    )


def draw_side_xz(ax, tp: Toolpath, *, max_segments: int = 6000) -> None:
    """Silhouette of every extruding move projected onto X–Z."""
    ax.clear()
    segs = [s for s in tp.segments if s.extruding]
    step = max(1, len(segs) // max_segments)
    for s in segs[::step]:
        ax.plot(
            [s.p0[0], s.p1[0]], [s.p0[2], s.p1[2]],
            color=_SILHOUETTE, lw=1.0, zorder=1,
        )
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Z (mm)")
    ax.set_title("side  X–Z", fontsize=9)


def draw_path_3d(ax, tp: Toolpath, *, max_segments: int = 8000) -> None:
    ax.clear()
    segs = [s for s in tp.segments if s.extruding]
    step = max(1, len(segs) // max_segments)
    for s in segs[::step]:
        ax.plot(
            [s.p0[0], s.p1[0]], [s.p0[1], s.p1[1]], [s.p0[2], s.p1[2]],
            color=_EXTRUDE, lw=0.7,
        )
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")


def draw_live_layer(ax, tp: Toolpath, layer: int) -> dict:
    """Static layer geometry (like `draw_layer_xy`) plus an empty nozzle-position
    marker artist for the panel's embedded live-print view. Returns
    `{"marker": Line2D}`; move it with `update_live_marker` on each poll tick
    instead of redrawing the whole layer, which is what makes per-tick updates
    cheap enough to run during a stream.
    """
    draw_layer_xy(ax, tp, layer)
    (marker,) = ax.plot([], [], "o", ms=7, color="#c53b3b", zorder=6)
    return {"marker": marker}


def update_live_marker(artists: dict, point: Point) -> None:
    artists["marker"].set_data([point[0]], [point[1]])


def progressive_path_3d(
    tp: Toolpath, current_line: int
) -> tuple[list[float], list[float], list[float]]:
    """X/Y/Z arrays of every *extruding* segment at or before `current_line` -
    "what the nozzle has actually printed so far" - with a `nan` break
    inserted wherever two consecutive extruding segments don't connect (a
    travel move in between), so a single `Line3D` can be reused every sync
    tick instead of a Line3D artist per segment (the old approach `draw_path_3d`
    still uses for a static one-shot snapshot). Segments are already
    line-ascending (single top-to-bottom parse), so this is a straight
    prefix-scan, no bisect needed - `current_line` shrinks the work as the
    print starts, not as it finishes.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    prev_end: Point | None = None
    for s in tp.segments:
        if s.line_no > current_line:
            break
        if not s.extruding:
            prev_end = None
            continue
        if prev_end != s.p0:
            if xs:
                xs.append(math.nan)
                ys.append(math.nan)
                zs.append(math.nan)
            xs.append(s.p0[0])
            ys.append(s.p0[1])
            zs.append(s.p0[2])
        xs.append(s.p1[0])
        ys.append(s.p1[1])
        zs.append(s.p1[2])
        prev_end = s.p1
    return xs, ys, zs


def draw_live_3d(ax, tp: Toolpath, bed_xy: tuple[float, float]) -> dict:
    """Isometric 3D view for the panel's live-print view: the full bed plate
    (static outline, `bed_xy` = `machine.x_max`/`y_max`) plus an empty path
    line - filled in progressively by `update_live_3d`, not drawn upfront
    like `draw_path_3d` - and a position marker. `set_box_aspect` gives true
    equal mm-per-axis scaling (matplotlib 3D defaults to stretching each axis
    to fill the view, which visually distorts a part that's wide and flat).
    """
    ax.clear()
    bx, by = bed_xy
    xr = max(tp.bbox_max[0], bx) - min(tp.bbox_min[0], 0.0)
    yr = max(tp.bbox_max[1], by) - min(tp.bbox_min[1], 0.0)
    zr = max(tp.bbox_max[2] - min(tp.bbox_min[2], 0.0), 1.0)
    ax.set_box_aspect((xr, yr, zr))
    bed_x = [0.0, bx, bx, 0.0, 0.0]
    bed_y = [0.0, 0.0, by, by, 0.0]
    bed_z = [0.0, 0.0, 0.0, 0.0, 0.0]
    ax.plot(bed_x, bed_y, bed_z, color="#9aa0a6", lw=1.0, ls="--", zorder=1)
    ax.view_init(elev=28, azim=-60)  # isometric-ish, matches most slicer previews
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    (path,) = ax.plot([], [], [], color=_EXTRUDE, lw=1.2, zorder=4)
    (marker,) = ax.plot([], [], [], "o", ms=6, color="#c53b3b", zorder=6)
    return {"path": path, "marker": marker}


def update_live_3d(artists: dict, tp: Toolpath, current_line: int) -> None:
    """Grow the printed-so-far path to `current_line` and move the marker to
    match - the 3D counterpart of `update_live_marker` (which only ever needs
    to move a dot, since `draw_live_layer` already draws the whole layer).

    `Line3D.set_3d_properties` re-reads its *original* x/y data via
    `get_xdata()` (not a recached copy), so passing plain lists through
    `set_data` leaves `_verts3d` holding plain lists too - matplotlib's own
    3D draw path then does `self._verts3d[0].shape` and blows up with
    `AttributeError: 'list' object has no attribute 'shape'`. Always hand it
    real arrays.
    """
    xs, ys, zs = progressive_path_3d(tp, current_line)
    artists["path"].set_data(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))
    artists["path"].set_3d_properties(np.asarray(zs, dtype=float))
    point = tp.progress_position(current_line)
    artists["marker"].set_data(np.asarray([point[0]]), np.asarray([point[1]]))
    artists["marker"].set_3d_properties(np.asarray([point[2]]))


def _project(pt: Point, plane: str) -> tuple[float, float]:
    return (pt[0], pt[1]) if plane == "xy" else (pt[0], pt[2])


def draw_insert_overlay(ax, moves, saved, config, *, plane: str = "xy") -> dict:
    """Draw the phase-coloured insert path on a 2D axes.

    Returns updatable artists: ``{"nozzle": Line2D, "pole": Line2D, "link": Line2D}``
    for the animation to move.
    """
    noz = nozzle_waypoints(moves, saved)
    pol = pole_waypoints(moves, saved, config)
    labels = phase_labels(moves)

    for i, phase in enumerate(labels):
        a, b = _project(noz[i], plane), _project(noz[i + 1], plane)
        ax.plot(
            [a[0], b[0]], [a[1], b[1]],
            color=PHASE_COLOR.get(phase, "#888"), lw=2.4, solid_capstyle="round",
            zorder=5,
        )
    px = [_project(p, plane) for p in pol]
    ax.plot(
        [p[0] for p in px], [p[1] for p in px],
        color=PHASE_COLOR["RESUME"], lw=1.2, ls=(0, (4, 3)), alpha=0.6, zorder=4,
    )

    n0 = _project(noz[0], plane)
    p0 = _project(pol[0], plane)
    (nozzle,) = ax.plot([n0[0]], [n0[1]], "o", ms=6, color="#111", zorder=7)
    (pole,) = ax.plot([p0[0]], [p0[1]], "o", ms=6, color=PHASE_COLOR["RESUME"], zorder=7)
    (link,) = ax.plot(
        [n0[0], p0[0]], [n0[1], p0[1]], color="#999", lw=1.0, ls=":", zorder=6
    )
    return {"nozzle": nozzle, "pole": pole, "link": link, "noz_pts": noz, "pol_pts": pol}


def update_insert_marker(artists: dict, t: float, plane: str = "xy") -> int:
    """Move the tip markers to fraction `t`; return the active segment index."""
    npt, seg = sample_polyline(artists["noz_pts"], t)
    ppt, _ = sample_polyline(artists["pol_pts"], t)
    n = _project(npt, plane)
    p = _project(ppt, plane)
    artists["nozzle"].set_data([n[0]], [n[1]])
    artists["pole"].set_data([p[0]], [p[1]])
    artists["link"].set_data([n[0], p[0]], [n[1], p[1]])
    return seg


def plan_for(mi: MagnetInsert, config: dict, saved: PrinterState) -> list[InsertMove]:
    return plan_insert_moves(mi, config, saved)
