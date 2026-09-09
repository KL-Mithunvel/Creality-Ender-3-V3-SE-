"""The magnet-insert sequence.

Fired by `GcodeRunner` when it sees the sentinel. Streaming is paused for the
duration (the printer just holds position and temperature). See
`.CLAUDE/CLAUDE.md` -> Architecture -> Insert sequence.

    SAVE      snapshot X Y Z E, feedrate, G90/G91, M82/M83, temps
    PARK      M83; retract; Z-hop to safe clearance; nozzle -> standby temp
    DISPENSE  dispenser.dispense()  (or operator "dispense" prompt if no dispenser)
    APPROACH  XY -> pocket_xy - magnet_tool_offset.xy      (envelope-checked)
    PRESS     Z -> seat_z - magnet_tool_offset.z   at press.feed;  dwell
    SHEAR     lateral shear.distance along shear_dir           (envelope-checked)
    LIFT      Z to safe clearance; move clear to the park point
    ASK       prompt("confirm") -> "success" | "retry" | "abort"
    RESUME    nozzle -> saved target (M109); XY/Z -> saved; un-retract; restore modes

Every phase transition is gated with `M400` (Marlin returns `ok` when a move is
*buffered*, not when it finishes). No `G28` anywhere (Development Rule 11).

`magnet_tool_offset` is (holding-pole position - nozzle-tip position). So the
carriage target is `pocket - offset` and, if the pole tip sits above the nozzle
tip (`offset.z > 0`), the nozzle presses down to `seat_z - offset.z`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..exceptions import OutOfEnvelopeError, SequenceAborted
from ..gcode.util import fmt_number as _fmt
from ..links.base import DispenserLink, PrinterLink
from ..state import MagnetInsert, PrinterState

log = logging.getLogger(__name__)

#: `prompt(stage)` where stage is "dispense" (-> "ready"/"abort") or
#: "confirm" (-> "success"/"retry"/"abort").
Prompt = Callable[[str], str]

_SHEAR_VEC: dict[str, tuple[float, float]] = {
    "+X": (1.0, 0.0),
    "-X": (-1.0, 0.0),
    "+Y": (0.0, 1.0),
    "-Y": (0.0, -1.0),
}


def _send(printer: PrinterLink, *lines: str) -> None:
    for line in lines:
        printer.command(line)


def insert_magnet(
    printer: PrinterLink,
    dispenser: DispenserLink | None,
    mi: MagnetInsert,
    config: dict,
    prompt: Prompt,
) -> None:
    """Park, embed one magnet, and leave the printer ready to resume printing.

    Raises `OutOfEnvelopeError` (before any move), `SequenceAborted`, or whatever
    the dispenser raises. On any failure the nozzle target is restored so the
    print stays resumable (Development Rule 5).
    """
    off = config["magnet_tool_offset"]
    machine = config["machine"]
    park = config["park"]
    press = config["press"]
    shear = config["shear"]
    retract = config["retract"]
    prime = config["prime"]
    temps = config["temps"]
    travel_feed = config["travel"]["feed"]
    max_retries = config.get("sequence", {}).get("max_retries", 3)

    carriage_x = mi.pocket_x - off["x"]
    carriage_y = mi.pocket_y - off["y"]
    press_z = mi.seat_z - off["z"]
    sdx, sdy = _SHEAR_VEC[mi.shear_dir]
    shear_x = carriage_x + sdx * shear["distance"]
    shear_y = carriage_y + sdy * shear["distance"]

    saved: PrinterState = printer.query_state()
    safe_z = saved.z + park["safe_z_lift_mm"]

    # --- envelope check: before ANY motion (Development Rule 12) ---------
    _check_envelope(
        ("approach X", carriage_x, machine["x_max"]),
        ("approach Y", carriage_y, machine["y_max"]),
        ("shear X", shear_x, machine["x_max"]),
        ("shear Y", shear_y, machine["y_max"]),
        ("press Z", press_z, machine["z_max"]),
        ("safe Z", safe_z, machine["z_max"]),
    )

    try:
        # --- PARK ------------------------------------------------------
        _send(
            printer,
            "M83",
            f"G1 E-{_fmt(retract['mm'])} F{_fmt(retract['feed'])}",
            "G90",
            f"G1 Z{_fmt(safe_z)} F{_fmt(travel_feed)}",
            "M400",
        )
        standby = temps.get("standby_nozzle_c")
        if standby is not None:
            _send(printer, f"M104 S{_fmt(standby)}")

        retries = 0
        while True:
            # --- DISPENSE --------------------------------------------
            if dispenser is not None:
                dispenser.dispense()
            elif prompt("dispense") != "ready":
                raise SequenceAborted("operator aborted at the dispense prompt")

            # --- APPROACH -------------------------------------------
            _send(
                printer,
                "G90",
                f"G1 X{_fmt(carriage_x)} Y{_fmt(carriage_y)} F{_fmt(travel_feed)}",
                "M400",
            )
            # --- PRESS ---------------------------------------------
            _send(
                printer,
                f"G1 Z{_fmt(press_z)} F{_fmt(press['feed'])}",
                f"G4 P{int(press['dwell_ms'])}",
                "M400",
            )
            # --- SHEAR -------------------------------------------
            _send(
                printer,
                f"G1 X{_fmt(shear_x)} Y{_fmt(shear_y)} F{_fmt(shear['feed'])}",
                "M400",
            )
            # --- LIFT -----------------------------------------
            _send(
                printer,
                f"G1 Z{_fmt(safe_z)} F{_fmt(travel_feed)}",
                f"G1 X{_fmt(park['x'])} Y{_fmt(park['y'])} F{_fmt(travel_feed)}",
                "M400",
            )

            decision = prompt("confirm")
            if decision == "success":
                break
            if decision == "abort":
                raise SequenceAborted("operator aborted at the confirm prompt")
            retries += 1
            if retries > max_retries:
                raise SequenceAborted(f"retry limit ({max_retries}) reached")
            log.warning("magnet insert retry %d/%d", retries, max_retries)
            if dispenser is not None:
                dispenser.reset()

        # --- RESUME --------------------------------------------
        target = saved.nozzle_target
        _send(printer, f"M104 S{_fmt(target)}")
        if temps.get("reheat_wait", True) and target > 0:
            _send(printer, f"M109 S{_fmt(target)}")
        _send(
            printer,
            "G90",
            f"G1 Z{_fmt(safe_z)} F{_fmt(travel_feed)}",
            f"G1 X{_fmt(saved.x)} Y{_fmt(saved.y)} F{_fmt(travel_feed)}",
            "M400",
            f"G1 Z{_fmt(saved.z)} F{_fmt(travel_feed)}",
            "M400",
            "M83",
            f"G1 E{_fmt(prime['mm'])} F{_fmt(prime['feed'])}",
            f"G92 E{_fmt(saved.e)}",           # restore the absolute-E reference
        )
        _send(printer, "M82" if saved.absolute_e else "M83")
        _send(printer, "G90" if saved.absolute_xyz else "G91")
        if saved.feedrate > 0:
            _send(printer, f"G1 F{_fmt(saved.feedrate)}")
        log.info(
            "magnet insert complete; printer restored to X%.2f Y%.2f Z%.2f",
            saved.x, saved.y, saved.z,
        )

    except SequenceAborted:
        _try(printer, "M104 S0")             # operator stopped — nozzle off
        raise
    except Exception:
        _try(printer, f"M104 S{_fmt(saved.nozzle_target)}")  # keep it resumable
        raise


def _check_envelope(*checks: tuple[str, float, float]) -> None:
    for name, value, hi in checks:
        if value < 0 or value > hi:
            raise OutOfEnvelopeError(
                f"{name} target {value:.2f} mm is outside [0, {hi}] — "
                "insert aborted, print left paused"
            )


def _try(printer: PrinterLink, line: str) -> None:
    """Best-effort send used only in error handlers."""
    try:
        printer.command(line)
    except Exception:  # pragma: no cover - defensive
        log.exception("failed to send %r during error handling", line)
