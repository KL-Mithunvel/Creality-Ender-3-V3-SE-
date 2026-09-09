"""Parse the magnet-insert sentinel comment.

Format: ``;MAGNET_INSERT X<x> Y<y> Z<seat_z> S<dir>`` where ``dir`` is one of
``+X -X +Y -Y``. It is a G-code comment, so a file carrying it still prints
normally from microSD. See `.CLAUDE/CLAUDE.md` -> Key Conventions.
"""

from __future__ import annotations

import re

from ..exceptions import SentinelParseError
from ..state import MagnetInsert

_FLOAT = r"(-?\d+(?:\.\d+)?)"
_FIELD_RE: dict[str, re.Pattern[str]] = {
    "X": re.compile(rf"\bX{_FLOAT}"),
    "Y": re.compile(rf"\bY{_FLOAT}"),
    "Z": re.compile(rf"\bZ{_FLOAT}"),
    "S": re.compile(r"\bS([+-][XY])\b"),
}


def parse_sentinel(line: str, token: str = ";MAGNET_INSERT") -> MagnetInsert | None:
    """Return a `MagnetInsert` if `line` is the sentinel, else `None`.

    Raises `SentinelParseError` if the line starts with `token` but a field is
    missing or malformed.
    """
    stripped = line.strip()
    if stripped != token and not stripped.startswith(token + " "):
        return None

    rest = stripped[len(token):]
    values: dict[str, str] = {}
    for name, rx in _FIELD_RE.items():
        match = rx.search(rest)
        if match is None:
            raise SentinelParseError(
                f"{token}: missing or malformed {name} field in {line!r}"
            )
        values[name] = match.group(1)

    try:
        return MagnetInsert(
            pocket_x=float(values["X"]),
            pocket_y=float(values["Y"]),
            seat_z=float(values["Z"]),
            shear_dir=values["S"],
            raw=stripped,
        )
    except ValueError as exc:  # e.g. shear_dir invariant in MagnetInsert
        raise SentinelParseError(f"{token}: {exc}") from exc
