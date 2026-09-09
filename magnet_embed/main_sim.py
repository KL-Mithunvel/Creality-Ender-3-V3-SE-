"""Simulation entry point (no hardware).

Headless:

    python -m magnet_embed.main_sim tests/data/sample.gcode
    python -m magnet_embed.main_sim tests/data/sample.gcode --confirm abort

With the Tkinter control panel:

    python -m magnet_embed.main_sim --gui
    python -m magnet_embed.main_sim --gui tests/data/sample.gcode
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .exceptions import SequenceAborted
from .gcode.runner import GcodeRunner
from .links.dispenser_sim import SimDispenser
from .links.printer_sim import SimPrinter
from .sequences.insert_magnet import insert_magnet
from .state import MagnetInsert

log = logging.getLogger("magnet_embed.main_sim")


def _make_on_sentinel(printer, dispenser, config, confirm: str):
    def _on_sentinel(mi: MagnetInsert) -> None:
        log.info(
            "SENTINEL  X%.3f Y%.3f Z%.3f S%s  -> running insert sequence",
            mi.pocket_x, mi.pocket_y, mi.seat_z, mi.shear_dir,
        )
        insert_magnet(
            printer, dispenser, mi, config,
            lambda stage: confirm if stage == "confirm" else "ready",
        )
        log.info("insert sequence done -> resuming stream")

    return _on_sentinel


def _run_headless(args, config) -> int:
    printer = SimPrinter()
    dispenser = SimDispenser()
    printer.connect()
    dispenser.connect()

    runner = GcodeRunner(
        printer, args.gcode,
        _make_on_sentinel(printer, dispenser, config, args.confirm), config,
    )
    log.info("streaming %s through SimPrinter", args.gcode)
    try:
        runner.run()
    except SequenceAborted as exc:
        log.error("run stopped: %s", exc)
        return 1

    st = printer.query_state()
    log.info(
        "done: %d/%d lines sent, %d sentinel(s), %d magnet(s); final X%.2f Y%.2f Z%.2f, nozzle %.0f/%.0f",
        runner.sent_lines, runner.total_lines, runner.sentinels_seen, dispenser.count,
        st.x, st.y, st.z, st.nozzle_temp, st.nozzle_target,
    )
    return 0


def _run_gui(args, config) -> int:
    from .app import Controller
    from .ui.panel import run_gui

    controller = Controller(SimPrinter(command_delay=0.03), SimDispenser(), config)
    controller.connect()
    if args.gcode:
        controller.load_gcode(args.gcode)
    run_gui(controller)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m magnet_embed.main_sim",
        description="Run the magnet-embedding assistant against the simulator.",
    )
    parser.add_argument("gcode", nargs="?", help="path to a .gcode file")
    parser.add_argument("--gui", action="store_true", help="open the Tkinter control panel")
    parser.add_argument("--config", default=None, help="override the config.yaml path")
    parser.add_argument(
        "--confirm", choices=("success", "retry", "abort"), default="success",
        help="headless: canned answer to the insert prompt (default: success)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)

    if args.gui:
        return _run_gui(args, config)
    if not args.gcode:
        parser.error("a .gcode file is required unless --gui is given")
    return _run_headless(args, config)


if __name__ == "__main__":
    sys.exit(main())
