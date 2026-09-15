"""Insert-motion geometry — the single source of truth for where the tool goes.

`insert_magnet` executes these targets as G-code; the visualisation (C16) and the
"Plan magnet insert" dialog (C17) draw and envelope-check the same numbers, so what
the operator previews is exactly what the printer will do.

`magnet_tool_offset` is (holding-pole tip) − (nozzle tip). The carriage is driven
to `pocket − offset.xy` and the nozzle pressed to `seat_z − offset.z`, so the pole
tip lands at the pocket centre / seat height.

`check_envelope` (C25) is the one damage guard for the insert (Dev Rules 7 and
12). It refuses, with a plain-language reason, anything that could hurt the
printer or the part: a pocket off the bed, a nozzle target outside the machine
limits, a press that would drive the nozzle into the build plate, and - when the
sliced toolpath is supplied - a press or shear that would drive the nozzle into
the partly-printed part (the pole is offset from the nozzle, so seating the
magnet puts the *nozzle* somewhere else, and with a pole above the nozzle it
goes *below* the seat height).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..state import MagnetInsert, PrinterState

if TYPE_CHECKING:  # avoid a runtime import cycle; only the type is needed here
    from ..gcode.toolpath import Toolpath

Point = tuple[float, float, float]

#: unit lateral vector for each shear direction
SHEAR_VEC: dict[str, tuple[float, float]] = {
    "+X": (1.0, 0.0),
    "-X": (-1.0, 0.0),
    "+Y": (0.0, 1.0),
    "-Y": (0.0, -1.0),
}

#: how many points along the SHEAR move are tested against the part footprint
#: (the endpoints alone can miss a short crossing of a footprint corner)
_SHEAR_SAMPLES = 10


@dataclass(frozen=True)
class Targets:
    """Nozzle-tip targets for one insert, in bed coordinates (mm)."""

    approach_xy: tuple[float, float]   # nozzle XY with the pole over the pocket
    press_z: float                     # nozzle Z at full press
    shear_xy: tuple[float, float]      # nozzle XY after the lateral shear
    safe_z: float                      # travel clearance above the saved Z


@dataclass(frozen=True)
class InsertMove:
    """One commanded move of the insert sequence (motion phases only)."""

    phase: str            # PARK APPROACH PRESS SHEAR LIFT CLEAR RESUME
    endpoint: Point       # nozzle-tip position after the move
    kind: str             # "travel" | "press" | "shear"
    feed: float           # mm/min


def compute_targets(mi: MagnetInsert, config: dict, saved: PrinterState) -> Targets:
    off = config["magnet_tool_offset"]
    ax = mi.pocket_x - off["x"]
    ay = mi.pocket_y - off["y"]
    press_z = mi.seat_z - off["z"]
    sdx, sdy = SHEAR_VEC[mi.shear_dir]
    dist = config["shear"]["distance"]
    shear_xy = (ax + sdx * dist, ay + sdy * dist)
    safe_z = saved.z + config["park"]["safe_z_lift_mm"]
    return Targets((ax, ay), press_z, shear_xy, safe_z)


def pole_point(nozzle: Point, config: dict) -> Point:
    """The holding-pole tip position for a given nozzle-tip position."""
    off = config["magnet_tool_offset"]
    return (nozzle[0] + off["x"], nozzle[1] + off["y"], nozzle[2] + off["z"])


def plan_insert_moves(
    mi: MagnetInsert, config: dict, saved: PrinterState
) -> list[InsertMove]:
    """Ordered nozzle-tip waypoints for PARK → APPROACH → PRESS → SHEAR → LIFT →
    CLEAR → RESUME. DISPENSE and the operator confirm are non-motion and omitted."""
    t = compute_targets(mi, config, saved)
    travel = config["travel"]["feed"]
    press_f = config["press"]["feed"]
    shear_f = config["shear"]["feed"]
    park = config["park"]
    sx, sy, sz = saved.x, saved.y, saved.z
    ax, ay = t.approach_xy
    shx, shy = t.shear_xy
    return [
        InsertMove("PARK", (sx, sy, t.safe_z), "travel", travel),
        InsertMove("APPROACH", (ax, ay, t.safe_z), "travel", travel),
        InsertMove("PRESS", (ax, ay, t.press_z), "press", press_f),
        InsertMove("SHEAR", (shx, shy, t.press_z), "shear", shear_f),
        InsertMove("LIFT", (shx, shy, t.safe_z), "travel", travel),
        InsertMove("CLEAR", (park["x"], park["y"], t.safe_z), "travel", travel),
        InsertMove("RESUME", (sx, sy, t.safe_z), "travel", travel),
        InsertMove("RESUME", (sx, sy, sz), "travel", travel),
    ]


# --- damage guard ---------------------------------------------------------

def part_footprint(toolpath: Toolpath, margin_mm: float) -> tuple[float, float, float, float]:
    """`(x0, y0, x1, y1)` of the printed part's XY extent, grown by `margin_mm`
    on every side. Uses the toolpath's bounding box - deliberately conservative
    (an L-shaped part is treated as its enclosing rectangle); a per-layer
    occupancy test is a later refinement (`TODO.md`)."""
    return (
        toolpath.bbox_min[0] - margin_mm,
        toolpath.bbox_min[1] - margin_mm,
        toolpath.bbox_max[0] + margin_mm,
        toolpath.bbox_max[1] + margin_mm,
    )


def _inside(xy: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = box
    return x0 <= xy[0] <= x1 and y0 <= xy[1] <= y1


def _points_along(
    a: tuple[float, float], b: tuple[float, float], n: int
) -> list[tuple[float, float]]:
    """`n + 1` evenly spaced points from `a` to `b`, endpoints included."""
    return [
        (a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
        for i in range(n + 1)
    ]


def _part_collisions(
    t: Targets, saved: PrinterState, config: dict, toolpath: Toolpath
) -> list[str]:
    """Would the nozzle enter the partly-printed part during PRESS or SHEAR?

    The part is printed up to `saved.z` when the sentinel fires (the layer the
    print is on). While the nozzle is over the part's footprint its tip must
    stay at least `collision.nozzle_clearance_mm` above that height. The pole
    tip touching the pocket is the *intended* contact and is not tested here.
    """
    coll = config["collision"]
    clearance = coll["nozzle_clearance_mm"]
    margin = coll["footprint_margin_mm"]
    printed_top = saved.z
    if t.press_z >= printed_top + clearance:
        return []                      # the nozzle never goes low enough to matter

    box = part_footprint(toolpath, margin)
    where: list[tuple[str, tuple[float, float]]] = [("PRESS", t.approach_xy)]
    where += [("SHEAR", p) for p in _points_along(t.approach_xy, t.shear_xy, _SHEAR_SAMPLES)[1:]]
    for phase, xy in where:
        if _inside(xy, box):
            off = config["magnet_tool_offset"]
            return [
                f"nozzle would enter the printed part during {phase}: nozzle "
                f"X{xy[0]:.2f} Y{xy[1]:.2f} is over the part footprint "
                f"(X {box[0]:.1f}..{box[2]:.1f}, Y {box[1]:.1f}..{box[3]:.1f}, "
                f"incl. {margin:g} mm margin) while press Z {t.press_z:.2f} mm is "
                f"below the printed top {printed_top:.2f} mm + {clearance:g} mm "
                f"clearance. With the pole {off['z']:g} mm above the nozzle the "
                f"pocket must sit within {abs(off['x']):g}/{abs(off['y']):g} mm "
                f"(X/Y) of a part edge, or the tool offset must change."
            ]
    return []


def check_envelope(
    mi: MagnetInsert,
    config: dict,
    saved: PrinterState,
    toolpath: Toolpath | None = None,
) -> list[str]:
    """Return one plain-language reason per problem that would make the insert
    unsafe (empty == OK). Checked, in order:

    1. the pocket itself lies on the bed;
    2. every nozzle target (approach, shear, safe Z) is inside the machine volume;
    3. the press would not drive the nozzle into the build plate (`press_z < 0`);
    4. with `toolpath` given, the press/shear would not drive the nozzle into
       the partly-printed part (`_part_collisions`).

    The dialog, the preview and `insert_magnet` all call this same function,
    so a plan that previews as OK is the plan that runs (Dev Rule 12).
    """
    t = compute_targets(mi, config, saved)
    m = config["machine"]
    off = config["magnet_tool_offset"]
    bad: list[str] = []

    for name, value, hi in (("pocket X", mi.pocket_x, m["x_max"]),
                            ("pocket Y", mi.pocket_y, m["y_max"])):
        if value < 0 or value > hi:
            bad.append(f"{name} {value:.2f} mm is outside the bed (0..{hi})")

    for name, value, hi in (
        ("approach X", t.approach_xy[0], m["x_max"]),
        ("approach Y", t.approach_xy[1], m["y_max"]),
        ("shear X", t.shear_xy[0], m["x_max"]),
        ("shear Y", t.shear_xy[1], m["y_max"]),
        ("safe Z", t.safe_z, m["z_max"]),
    ):
        if value < 0 or value > hi:
            bad.append(
                f"{name} {value:.2f} mm (nozzle) is outside the machine limit 0..{hi} "
                f"- the tool offset pushes the carriage out of range"
            )

    if t.press_z > m["z_max"]:
        bad.append(f"press Z {t.press_z:.2f} mm (nozzle) is above the machine limit {m['z_max']}")
    if t.press_z < 0:
        bad.append(
            f"nozzle would hit the build plate: press Z {t.press_z:.2f} mm "
            f"(seat Z {mi.seat_z:g} − offset Z {off['z']:g}) is below 0"
        )

    if toolpath is not None:
        bad += _part_collisions(t, saved, config, toolpath)
    return bad
