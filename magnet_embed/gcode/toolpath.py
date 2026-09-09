"""Parse a G-code file into a drawable, measurable toolpath.

Used by the visualisation (C16) and the insert-planning dialog (C17). Pure and
dependency-free; shares helpers with the sim link and the post-processor.

Layers come from slicer markers when the file has them (`;LAYER:` /
`;LAYER_CHANGE` + `;Z:` — via `postprocess._detect_layers`). A file with no
markers is layered by Z instead: a new layer starts whenever an *extruding* move
raises Z above the current layer height (travel Z-hops do not count).
"""

from __future__ import annotations

import bisect
import math
import re
from dataclasses import dataclass
from pathlib import Path

from .postprocess import _detect_layers
from .util import parse_words, strip_comment

_EPS = 1e-4
_HEAD_RE = re.compile(r"^([GM]\d+)", re.IGNORECASE)

Point = tuple[float, float, float]


@dataclass(frozen=True)
class Segment:
    """One G0/G1 move: from `p0` to `p1`, in bed coordinates (mm)."""

    p0: Point
    p1: Point
    extruding: bool          # filament advancing while XY moves (a printed line)
    layer: int               # 0-based layer index
    feed: float              # mm/min in effect for this move (0 if never set)

    @property
    def length(self) -> float:
        return math.dist(self.p0, self.p1)


@dataclass
class Toolpath:
    segments: list[Segment]
    layer_z: list[float]        # height of each layer index, ascending
    bbox_min: Point            # over extruding moves (falls back to all moves)
    bbox_max: Point

    @property
    def layer_count(self) -> int:
        return len(self.layer_z)

    @property
    def move_count(self) -> int:
        return len(self.segments)

    @property
    def top_z(self) -> float:
        return self.layer_z[-1] if self.layer_z else self.bbox_max[2]

    def extrude_distance(self) -> float:
        return sum(s.length for s in self.segments if s.extruding)

    def travel_distance(self) -> float:
        return sum(s.length for s in self.segments if not s.extruding)

    def est_time_s(self) -> float:
        """Rough print time: Σ length ÷ feed. Ignores acceleration and dwells."""
        return sum(
            s.length / (s.feed / 60.0)
            for s in self.segments
            if s.feed > 0 and s.length > 0
        )

    def segments_in_layer(self, layer: int) -> list[Segment]:
        return [s for s in self.segments if s.layer == layer]

    def layer_for_z(self, z: float) -> int:
        """Index of the first layer whose height is >= `z` (clamped to the top)."""
        for i, lz in enumerate(self.layer_z):
            if lz >= z - _EPS:
                return i
        return max(0, self.layer_count - 1)


def parse_toolpath(path: str | Path) -> Toolpath:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    markers = _detect_layers(lines)
    marker_mode = bool(markers)
    marker_ends = [m.marker_end for m in markers]
    marker_z: list[float | None] = [m.z for m in markers]

    x = y = z = e = 0.0
    abs_xyz = True
    abs_e = True
    feed = 0.0
    z_layers: list[float] = []     # Z-heuristic layer heights (marker_mode == False)
    seen_layer_z: dict[int, float] = {}   # first extruding Z per layer (marker_mode)
    cur_layer = 0
    segments: list[Segment] = []
    emin = [math.inf, math.inf, math.inf]
    emax = [-math.inf, -math.inf, -math.inf]
    amin = [math.inf, math.inf, math.inf]
    amax = [-math.inf, -math.inf, -math.inf]

    for i, raw in enumerate(lines):
        code = strip_comment(raw).strip()
        if not code:
            continue
        m = _HEAD_RE.match(code)
        if m is None:
            continue
        head = m.group(1).upper()

        if head == "G90":
            abs_xyz = True
            continue
        if head == "G91":
            abs_xyz = False
            continue
        if head == "M82":
            abs_e = True
            continue
        if head == "M83":
            abs_e = False
            continue

        w = parse_words(code)

        if head == "G92":
            x = w.get("X", x)
            y = w.get("Y", y)
            z = w.get("Z", z)
            e = w.get("E", e)
            continue
        if head == "G28":
            axes = {t[0] for t in code.upper().split()[1:] if t[:1] in ("X", "Y", "Z")}
            if not axes or "X" in axes:
                x = 0.0
            if not axes or "Y" in axes:
                y = 0.0
            if not axes or "Z" in axes:
                z = 0.0
            continue
        if head not in ("G0", "G1"):
            continue

        if "F" in w:
            feed = w["F"]
        nx = w["X"] if ("X" in w and abs_xyz) else x + w.get("X", 0.0)
        ny = w["Y"] if ("Y" in w and abs_xyz) else y + w.get("Y", 0.0)
        nz = w["Z"] if ("Z" in w and abs_xyz) else z + w.get("Z", 0.0)
        ne = (w["E"] if abs_e else e + w["E"]) if "E" in w else e

        xy_moved = abs(nx - x) > _EPS or abs(ny - y) > _EPS
        moved = xy_moved or abs(nz - z) > _EPS
        extruding = (ne - e) > _EPS and xy_moved

        if marker_mode:
            k = bisect.bisect_right(marker_ends, i) - 1
            cur_layer = k if k >= 0 else 0
            if extruding:
                seen_layer_z.setdefault(cur_layer, nz)
        elif extruding:
            if not z_layers:
                z_layers.append(round(nz, 4))
            elif nz > z_layers[-1] + _EPS:
                z_layers.append(round(nz, 4))
            cur_layer = len(z_layers) - 1

        if moved:
            segments.append(Segment((x, y, z), (nx, ny, nz), extruding, max(cur_layer, 0), feed))
            for pt in ((x, y, z), (nx, ny, nz)):
                for c in range(3):
                    amin[c] = min(amin[c], pt[c])
                    amax[c] = max(amax[c], pt[c])
                    if extruding:
                        emin[c] = min(emin[c], pt[c])
                        emax[c] = max(emax[c], pt[c])

        x, y, z, e = nx, ny, nz, ne

    # --- layer_z table -------------------------------------------------
    if marker_mode:
        layer_z: list[float] = []
        for k in range(len(markers)):
            zk = marker_z[k]
            if zk is None:
                zk = seen_layer_z.get(k)
            if zk is None:
                zk = layer_z[-1] if layer_z else 0.0
            layer_z.append(round(zk, 4))
    else:
        layer_z = z_layers or [round(z, 4)]

    has_extrude = emin[0] != math.inf
    bmin = tuple(emin) if has_extrude else tuple(amin)
    bmax = tuple(emax) if has_extrude else tuple(amax)
    if bmin[0] == math.inf:  # no moves at all
        bmin = bmax = (0.0, 0.0, 0.0)
    return Toolpath(segments, layer_z, bmin, bmax)  # type: ignore[arg-type]
