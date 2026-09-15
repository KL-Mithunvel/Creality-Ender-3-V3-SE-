"""In-process fake Ender-3 V3 SE.

Parses a useful subset of G-code, tracks position / temps / modal state, and
acknowledges every line with `ok`. Same idea as OctoPrint's virtual printer
(see `project/BUILD_PLAN.md` -> References). Fault injection (delayed ok, resend,
busy) is added in build chunk C5 for testing the real serial link.
"""

from __future__ import annotations

import time
from collections import deque

from ..exceptions import AckTimeout, PrinterConnectionError, PrinterError
from ..gcode.util import parse_words, strip_comment
from ..state import PrinterState
from .base import PrinterLink

_Move = tuple[float, float, float, float]  # x, y, z, e after the move


class SimPrinter(PrinterLink):
    """Simulated printer. `sent` and `moves` are exposed for test assertions.

    `command_delay` sleeps that many seconds per line — set it non-zero to make a
    streamed run take real time (useful for the GUI and for threading tests).
    """

    def __init__(
        self,
        *,
        home: tuple[float, float, float] = (0.0, 0.0, 0.0),
        command_delay: float = 0.0,
    ) -> None:
        self.state = PrinterState()
        self._home = home
        self._delay = command_delay
        self._acks: deque[str] = deque()
        self.sent: list[str] = []      # every line received, verbatim
        self.moves: list[_Move] = []   # (x, y, z, e) after each move/home
        self.halted = False            # set by M112, cleared by M999 (like Marlin)

    # --- PrinterLink -----------------------------------------------------

    def connect(self) -> None:
        self.state.connected = True

    def disconnect(self) -> None:
        self.state.connected = False

    def send_line(self, line: str) -> None:
        if not self.state.connected:
            raise PrinterConnectionError("SimPrinter.send_line() before connect()")
        if self._delay:
            time.sleep(self._delay)
        code = strip_comment(line).strip()
        head = code.split()[0].upper() if code else ""
        if self.halted and head != "M999":
            # a real Marlin board answers nothing useful after M112 until it is
            # reset; surface that as the same error type the serial link would
            raise PrinterError("printer halted by M112 - send M999 or power-cycle, then reconnect")
        self.sent.append(line)
        self._execute(code)
        self._acks.append(self._ok_payload())

    def wait_ok(self, timeout_s: float | None = None) -> str:
        if not self._acks:
            raise AckTimeout("SimPrinter.wait_ok() with no line awaiting acknowledgement")
        return self._acks.popleft()

    def query_state(self) -> PrinterState:
        return self.state.copy()

    # --- internals ----------------------------------------------------

    def _ok_payload(self) -> str:
        s = self.state
        return (
            f"ok T:{s.nozzle_temp:.1f} /{s.nozzle_target:.1f} "
            f"B:{s.bed_temp:.1f} /{s.bed_target:.1f}"
        )

    def _execute(self, code: str) -> None:
        if not code:
            return
        head = code.split()[0].upper()
        w = parse_words(code)
        s = self.state

        if head in ("G0", "G1"):
            self._move(w)
        elif head == "G28":
            self._home_axes(code)
        elif head == "G90":
            s.absolute_xyz = True
        elif head == "G91":
            s.absolute_xyz = False
        elif head == "G92":
            for axis, attr in (("X", "x"), ("Y", "y"), ("Z", "z"), ("E", "e")):
                if axis in w:
                    setattr(s, attr, w[axis])
        elif head == "M82":
            s.absolute_e = True
        elif head == "M83":
            s.absolute_e = False
        elif head in ("M104", "M109"):
            if "S" in w:
                s.nozzle_target = w["S"]
                s.nozzle_temp = w["S"]     # sim: instantaneous
        elif head in ("M140", "M190"):
            if "S" in w:
                s.bed_target = w["S"]
                s.bed_temp = w["S"]
        elif head == "M112":
            # emergency stop: heaters + steppers off, firmware halts until reset
            s.nozzle_target = s.bed_target = 0.0
            self.halted = True
        elif head == "M999":
            self.halted = False
        # M105 / M114 / M115 / M155 / M400 / everything else: nothing to model,
        # but the line is still acknowledged.

    def _move(self, w: dict[str, float]) -> None:
        s = self.state
        if "F" in w:
            s.feedrate = w["F"]
        moved = any(axis in w for axis in ("X", "Y", "Z", "E"))
        if s.absolute_xyz:
            for axis, attr in (("X", "x"), ("Y", "y"), ("Z", "z")):
                if axis in w:
                    setattr(s, attr, w[axis])
        else:
            s.x += w.get("X", 0.0)
            s.y += w.get("Y", 0.0)
            s.z += w.get("Z", 0.0)
        if "E" in w:
            s.e = w["E"] if s.absolute_e else s.e + w["E"]
        if moved:
            self.moves.append((s.x, s.y, s.z, s.e))

    def _home_axes(self, code: str) -> None:
        s = self.state
        hx, hy, hz = self._home
        # G28 axis args may be bare letters ("G28 X") so parse_words misses them.
        tokens = code.upper().split()[1:]
        wants = {t[0] for t in tokens if t and t[0] in ("X", "Y", "Z")}
        if not wants:
            wants = {"X", "Y", "Z"}
        if "X" in wants:
            s.x = hx
        if "Y" in wants:
            s.y = hy
        if "Z" in wants:
            s.z = hz
        s.homed = True
        self.moves.append((s.x, s.y, s.z, s.e))
