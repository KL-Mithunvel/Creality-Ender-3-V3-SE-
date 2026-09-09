"""Inject the magnet sentinel into a sliced G-code file.

Adds one comment line

    ;MAGNET_INSERT X<px> Y<py> Z<seat_z> S<dir>

at the start of a chosen layer. Because it is a comment the output file still
prints normally from microSD; our `GcodeRunner` detects it and runs the insert
sequence instead of sending it.

Slicer markers understood:
  * Cura / Creality Print : ``;LAYER:<n>``          (layer height from the first Z move)
  * PrusaSlicer / SuperSlicer : ``;LAYER_CHANGE`` then ``;Z:<height>``

CLI::

    python -m magnet_embed.gcode.postprocess IN.gcode (--layer N | --z H) \
        --xy PX PY --seat-z SZ --shear +X|-X|+Y|-Y [-o OUT.gcode]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ..exceptions import PostprocessError
from ..gcode.util import fmt_number
from ..state import SHEAR_DIRS

_CURA_LAYER_RE = re.compile(r";\s*LAYER:\s*(-?\d+)")
_PRUSA_Z_RE = re.compile(r";\s*Z:\s*([0-9]+(?:\.[0-9]+)?)")
_Z_MOVE_RE = re.compile(r"^G[01]\b.*?\bZ([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


@dataclass
class _Layer:
    number: int          # Cura layer index, or 0-based ordinal for PrusaSlicer
    marker_start: int    # line index of the ";LAYER:" / ";LAYER_CHANGE" line
    marker_end: int      # last line of the marker block (";Z:" for Prusa, else == start)
    z: float | None      # layer height in mm, if known


def _detect_layers(lines: list[str]) -> list[_Layer]:
    layers: list[_Layer] = []
    prusa_pending: int | None = None    # index into `layers` awaiting its ;Z:

    for i, raw in enumerate(lines):
        s = raw.strip()

        cura = _CURA_LAYER_RE.match(s)
        if cura:
            layers.append(_Layer(int(cura.group(1)), i, i, None))
            prusa_pending = None
            continue

        if s == ";LAYER_CHANGE" or s == "; LAYER_CHANGE":
            layers.append(_Layer(len(layers), i, i, None))
            prusa_pending = len(layers) - 1
            continue

        z_comment = _PRUSA_Z_RE.match(s)
        if z_comment and prusa_pending is not None:
            layers[prusa_pending].z = float(z_comment.group(1))
            layers[prusa_pending].marker_end = i
            prusa_pending = None
            continue

        if layers and layers[-1].z is None:
            z_move = _Z_MOVE_RE.match(s)
            if z_move:
                layers[-1].z = float(z_move.group(1))

    return layers


def inject_sentinel(
    in_path: str | Path,
    out_path: str | Path,
    *,
    pocket_xy: tuple[float, float],
    seat_z: float,
    shear: str,
    layer: int | None = None,
    z_mm: float | None = None,
    emit_pause: bool = False,
) -> int:
    """Write `in_path` to `out_path` with one sentinel added. Return its 1-based line no.

    Pass exactly one of `layer` (match a ``;LAYER:`` index / a ``;LAYER_CHANGE``
    ordinal) or `z_mm` (first layer whose height >= this). With `emit_pause`, a real
    ``M0`` is written just before the sentinel so the file also pauses when printed
    straight from microSD.
    """
    if (layer is None) == (z_mm is None):
        raise ValueError("pass exactly one of layer= or z_mm=")
    if shear not in SHEAR_DIRS:
        raise ValueError(f"shear must be one of {SHEAR_DIRS}, got {shear!r}")

    lines = Path(in_path).read_text(encoding="utf-8").splitlines()
    layers = _detect_layers(lines)
    if not layers:
        raise PostprocessError(
            f"{in_path}: no ;LAYER: or ;LAYER_CHANGE markers found — cannot place the sentinel"
        )

    if layer is not None:
        matches = [lyr for lyr in layers if lyr.number == layer]
        if not matches:
            span = f"{layers[0].number}..{layers[-1].number}"
            raise PostprocessError(f"layer {layer} not found (file has layers {span})")
        target = matches[0]
    else:
        with_z = [lyr for lyr in layers if lyr.z is not None and lyr.z >= z_mm]
        if not with_z:
            known = [lyr.z for lyr in layers if lyr.z is not None]
            top = max(known) if known else "unknown"
            raise PostprocessError(f"no layer with Z >= {z_mm} (top layer Z is {top})")
        target = with_z[0]

    px, py = pocket_xy
    sentinel = (
        f";MAGNET_INSERT X{fmt_number(px)} Y{fmt_number(py)} "
        f"Z{fmt_number(seat_z)} S{shear}"
    )
    new_lines = ["M0 ; magnet insert — resume when the magnet is seated"] if emit_pause else []
    new_lines.append(sentinel)
    insert_at = target.marker_end + 1
    out_lines = lines[:insert_at] + new_lines + lines[insert_at:]
    Path(out_path).write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return insert_at + len(new_lines)   # 1-based line number of the sentinel


def _default_out(in_path: str) -> str:
    p = Path(in_path)
    return str(p.with_suffix(".magnet" + p.suffix))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m magnet_embed.gcode.postprocess",
        description="Inject a ;MAGNET_INSERT sentinel into a sliced G-code file.",
    )
    parser.add_argument("gcode", help="input .gcode file")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--layer", type=int, help="layer index (Cura) / ordinal (PrusaSlicer)")
    where.add_argument("--z", type=float, dest="z_mm", help="first layer with height >= this (mm)")
    parser.add_argument("--xy", type=float, nargs=2, metavar=("PX", "PY"), required=True,
                        help="pocket centre on the bed (mm)")
    parser.add_argument("--seat-z", type=float, required=True, dest="seat_z",
                        help="magnet seat height = pocket floor + magnet thickness (mm)")
    parser.add_argument("--shear", choices=SHEAR_DIRS, required=True,
                        help="direction to slide the tool off the seated magnet")
    parser.add_argument("--pause", action="store_true",
                        help="also write a real M0 before the sentinel (pause on microSD prints)")
    parser.add_argument("-o", "--out", default=None, help="output file (default: *.magnet.gcode)")
    args = parser.parse_args(argv)

    out = args.out or _default_out(args.gcode)
    try:
        line_no = inject_sentinel(
            args.gcode, out,
            pocket_xy=(args.xy[0], args.xy[1]),
            seat_z=args.seat_z, shear=args.shear,
            layer=args.layer, z_mm=args.z_mm, emit_pause=args.pause,
        )
    except (PostprocessError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {out} (sentinel at line {line_no})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
