"""Plain data structures: printer state snapshot and the parsed sentinel."""

from __future__ import annotations

from dataclasses import dataclass, replace

#: Valid values for the sentinel's shear-direction field.
SHEAR_DIRS = ("+X", "-X", "+Y", "-Y")


@dataclass
class PrinterState:
    """A best-effort snapshot of the printer. Mutated in place by the sim link."""

    connected: bool = False
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    e: float = 0.0
    nozzle_temp: float = 0.0
    nozzle_target: float = 0.0
    bed_temp: float = 0.0
    bed_target: float = 0.0
    absolute_xyz: bool = True   # G90 (True) / G91 (False)
    absolute_e: bool = True     # M82 (True) / M83 (False)
    feedrate: float = 0.0       # mm/min, last F word seen
    homed: bool = False

    def copy(self) -> "PrinterState":
        return replace(self)


@dataclass
class MagnetInsert:
    """Parsed `;MAGNET_INSERT X<x> Y<y> Z<z> S<dir>` sentinel.

    Coordinates are in bed space. `seat_z` is the magnet's seat height
    (pocket floor + magnet thickness). `shear_dir` is one of `SHEAR_DIRS`.
    """

    pocket_x: float
    pocket_y: float
    seat_z: float
    shear_dir: str
    raw: str = ""

    def __post_init__(self) -> None:
        if self.shear_dir not in SHEAR_DIRS:
            raise ValueError(
                f"shear_dir must be one of {SHEAR_DIRS}, got {self.shear_dir!r}"
            )

    @property
    def pocket_xy(self) -> tuple[float, float]:
        return (self.pocket_x, self.pocket_y)
