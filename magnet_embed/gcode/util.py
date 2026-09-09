"""Small, dependency-free G-code text helpers used by the sim link and the runner."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"([A-Za-z])\s*(-?\d*\.?\d+)")


def strip_comment(line: str) -> str:
    """Return `line` with any `;` comment removed (Marlin: `;` runs to end of line)."""
    idx = line.find(";")
    return line if idx < 0 else line[:idx]


def parse_words(line: str) -> dict[str, float]:
    """`"G1 X10 Y-5 F1200"` -> `{'G': 1.0, 'X': 10.0, 'Y': -5.0, 'F': 1200.0}`.

    The comment (if any) is stripped first. Duplicate letters keep the last value.
    """
    return {
        m.group(1).upper(): float(m.group(2))
        for m in _WORD_RE.finditer(strip_comment(line))
    }


def fmt_number(value: float) -> str:
    """Format a float for G-code / a sentinel: 3 dp, trailing zeros trimmed, never empty."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-", "-0") else "0"
