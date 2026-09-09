"""Headless simulation entry point.

Streams a G-code file through `SimPrinter` with no hardware attached. At the
sentinel it runs the real `insert_magnet` sequence against `SimPrinter` +
`SimDispenser`.

    python -m magnet_embed.main_sim tests/data/sample.gcode
    python -m magnet_embed.main_sim tests/data/sample.gcode --confirm abort
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
            printer,
            dispenser,
            mi,
            config,
            lambda stage: confirm if stage == "confirm" else "ready",
        )
        log.info("insert sequence done -> resuming stream")

    return _on_sentinel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m magnet_embed.main_sim",
        description="Stream a G-code file through the simulated printer (no hardware).",
    )
    parser.add_argument("gcode", help="path to a .gcode file")
    parser.add_argument("--config", default=None, help="override the config.yaml path")
    parser.add_argument(
        "--confirm",
        choices=("success", "retry", "abort"),
        default="success",
        help="canned answer to the insert confirmation prompt (default: success)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)

    printer = SimPrinter()
    dispenser = SimDispenser()
    printer.connect()
    dispenser.connect()

    runner = GcodeRunner(
        printer, args.gcode, _make_on_sentinel(printer, dispenser, config, args.confirm), config
    )
    log.info("streaming %s through SimPrinter", args.gcode)
    try:
        runner.run()
    except SequenceAborted as exc:
        log.error("run stopped: %s", exc)
        return 1

    st = printer.query_state()
    log.info(
        "done: %d/%d lines sent, %d sentinel(s), %d magnet(s) dispensed; "
        "final pos X%.2f Y%.2f Z%.2f, nozzle %.0f/%.0f",
        runner.sent_lines,
        runner.total_lines,
        runner.sentinels_seen,
        dispenser.count,
        st.x,
        st.y,
        st.z,
        st.nozzle_temp,
        st.nozzle_target,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
