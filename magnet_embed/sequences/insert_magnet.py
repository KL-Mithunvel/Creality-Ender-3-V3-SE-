"""The magnet-insert sequence.

STUB — the body is implemented in build chunk C2. The signature and the state
machine are fixed here so the rest of the code (GcodeRunner's `on_sentinel`, the
UI) can be built against them.
"""

from __future__ import annotations

from collections.abc import Callable

from ..links.base import DispenserLink, PrinterLink
from ..state import MagnetInsert

#: `prompt()` returns one of "success", "retry", "abort".
Prompt = Callable[[], str]


def insert_magnet(
    printer: PrinterLink,
    dispenser: DispenserLink | None,
    mi: MagnetInsert,
    config: dict,
    prompt: Prompt,
) -> None:
    """Park, embed one magnet, and return the printer ready to resume printing.

    State machine (see `.CLAUDE/CLAUDE.md` -> Architecture -> Insert sequence and
    `project/PROJECT_PLAN.md` section 4). Every phase transition is gated with
    `M400`; no `G28` anywhere (Development Rule 11).

        SAVE      record X Y Z E, feedrates, G90/G91, M82/M83, temps
        PARK      M83; retract; Z-hop to safe clearance; nozzle -> standby temp
        DISPENSE  dispenser.dispense()  (or operator prompt when dispenser is None)
        APPROACH  XY -> pocket_xy - magnet_tool_offset.xy   (envelope-checked)
        PRESS     Z -> seat_z + magnet_tool_offset.z   at press.feed
        SHEAR     lateral shear.distance along shear_dir
        LIFT      Z to safe clearance; move clear of the part
        ASK       prompt() -> success | retry | abort
        RESUME    nozzle -> print temp (M109); XY/Z -> saved; un-retract; restore modes

    Raises `OutOfEnvelopeError`, `SequenceAborted`, `DispenserError`; on any failure
    it restores nozzle temp and leaves the printer resumable (Development Rule 5).
    """
    raise NotImplementedError("insert_magnet is implemented in build chunk C2")
