"""Shared entry-point building blocks: build links, ping, run headless, launch the panel.

The CLIs — root ``main.py`` and ``magnet_embed.main`` / ``main_printer`` / ``main_sim``
— differ only in their argument surface. The wiring lives here once so link
construction and the ``--ping`` smoke test are not copy-pasted (DRY — PROJ_STARTER).

Mode is chosen by the caller, never by a runtime flag inside the links:

  * ``sim``      — ``SimPrinter`` + ``SimDispenser`` (safe on any machine)
  * ``printer``  — real ``SerialPrinter``, ``dispenser=None``
  * ``hardware`` — real ``SerialPrinter`` + real ``SerialDispenser``
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger("magnet_embed.entry")

MODES = ("sim", "printer", "hardware")


def build_links(
    mode: str,
    config: dict,
    *,
    with_dispenser: bool = True,
    command_delay: float = 0.03,
):
    """Return ``(printer, dispenser)`` for ``mode``; ``dispenser`` is ``None`` when not wired.

    Serial link classes are imported lazily so ``mode="sim"`` never touches the
    ``*_serial`` modules.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")

    if mode == "sim":
        from .links.dispenser_sim import SimDispenser
        from .links.printer_sim import SimPrinter

        printer = SimPrinter(command_delay=command_delay)
        return printer, (SimDispenser() if with_dispenser else None)

    from .links.printer_serial import SerialPrinter

    p = config["printer"]
    printer = SerialPrinter(
        p["port"],
        p["baud"],
        ack_timeout_s=p["ack_timeout_s"],
        connect_settle_s=p.get("connect_settle_s", 2.0),
    )
    if mode == "printer" or not with_dispenser:
        return printer, None

    from .links.dispenser_serial import SerialDispenser

    d = config["dispenser"]
    dispenser = SerialDispenser(
        d["port"], d["baud"], reset_settle_s=d.get("reset_settle_s", 2.5)
    )
    return printer, dispenser


def ping(printer, dispenser) -> int:
    """Connect to each device, print a one-line status, disconnect. Return an exit code."""
    rc = 0
    try:
        printer.connect()
        st = printer.query_state()
        print(
            f"printer OK: X{st.x} Y{st.y} Z{st.z} "
            f"nozzle {st.nozzle_temp}/{st.nozzle_target}"
        )
        printer.disconnect()
    except Exception as exc:  # noqa: BLE001 - report any failure and exit non-zero
        print(f"printer FAIL: {exc}", file=sys.stderr)
        rc = 1

    if dispenser is None:
        print("dispenser SKIPPED")
    else:
        try:
            dispenser.connect()
            print(f"dispenser OK: status {dispenser.status()}")
            dispenser.disconnect()
        except Exception as exc:  # noqa: BLE001
            print(f"dispenser FAIL: {exc}", file=sys.stderr)
            rc = 1
    return rc


def run_headless(
    printer,
    dispenser,
    config: dict,
    gcode: str | Path,
    *,
    confirm: str = "success",
) -> int:
    """Stream ``gcode`` with no UI; answer the insert prompt with ``confirm``.

    ``confirm`` is one of ``success`` / ``retry`` / ``abort`` (used only at the
    ``"confirm"`` stage; the dispense prompt always gets ``"ready"``).
    """
    from .exceptions import SequenceAborted
    from .gcode.runner import GcodeRunner
    from .sequences.insert_magnet import insert_magnet
    from .state import MagnetInsert

    printer.connect()
    if dispenser is not None:
        dispenser.connect()

    def on_sentinel(mi: MagnetInsert) -> None:
        log.info(
            "SENTINEL X%.2f Y%.2f Z%.2f S%s -> insert sequence",
            mi.pocket_x, mi.pocket_y, mi.seat_z, mi.shear_dir,
        )
        insert_magnet(
            printer, dispenser, mi, config,
            lambda stage: confirm if stage == "confirm" else "ready",
        )

    runner = GcodeRunner(printer, gcode, on_sentinel, config)
    log.info("streaming %s", gcode)
    try:
        runner.run()
    except SequenceAborted as exc:
        log.error("run stopped: %s", exc)
        return 1

    st = printer.query_state()
    log.info(
        "done: %d/%d lines, %d sentinel(s); final X%.2f Y%.2f Z%.2f",
        runner.sent_lines, runner.total_lines, runner.sentinels_seen, st.x, st.y, st.z,
    )
    return 0


def launch_panel(
    printer,
    dispenser,
    config: dict,
    *,
    dispenser_optional: bool,
    gcode: str | Path | None = None,
    log_dir: str | None = "logs",
) -> int:
    """Connect, then run the Tkinter panel. Return an exit code."""
    from .app import Controller
    from .exceptions import PrinterConnectionError
    from .ui.panel import run_gui

    controller = Controller(
        printer, dispenser, config,
        log_dir=log_dir, dispenser_optional=dispenser_optional,
    )
    try:
        controller.connect()
    except PrinterConnectionError as exc:
        log.error("connect failed: %s", exc)
        return 1
    if gcode:
        controller.load_gcode(gcode)
    run_gui(controller)
    return 0
