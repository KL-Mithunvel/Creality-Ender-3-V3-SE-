"""Insert-motion geometry — the single source of truth for where the tool goes.

`insert_magnet` executes these targets as G-code; the visualisation (C16) and the
"Plan magnet insert" dialog (C17) draw and envelope-check the same numbers, so what
the operator previews is exactly what the printer will do.

`magnet_tool_offset` is (holding-pole tip) − (nozzle tip). The carriage is driven
to `pocket − offset.xy` and the nozzle pressed to `seat_z − offset.z`, so the pole
tip lands at the pocket centre / seat height.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..state import MagnetInsert, PrinterState

Point = tuple[float, float, float]

#: unit lateral vector for each shear direction
SHEAR_VEC: dict[str, tuple[float, float]] = {
    "+X": (1.0, 0.0),
    "-X": (-1.0, 0.0),
    "+Y": (0.0, 1.0),
    "-Y": (0.0, -1.0),
}


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


def check_envelope(
    mi: MagnetInsert, config: dict, saved: PrinterState
) -> list[str]:
    """Return a label for every target outside the machine volume (empty == OK)."""
    t = compute_targets(mi, config, saved)
    m = config["machine"]
    checks = (
        ("approach X", t.approach_xy[0], m["x_max"]),
        ("approach Y", t.approach_xy[1], m["y_max"]),
        ("shear X", t.shear_xy[0], m["x_max"]),
        ("shear Y", t.shear_xy[1], m["y_max"]),
        ("press Z", t.press_z, m["z_max"]),
        ("safe Z", t.safe_z, m["z_max"]),
    )
    return [
        f"{name} {value:.2f} mm (limit 0..{hi})"
        for name, value, hi in checks
        if value < 0 or value > hi
    ]
