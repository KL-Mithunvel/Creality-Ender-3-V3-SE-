"""Headless simulation entry point.

Streams a G-code file through `SimPrinter` with no hardware attached. At the
sentinel it just logs the parsed fields (the real insert sequence lands in C2).

    python -m magnet_embed.main_sim tests/data/sample.gcode
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .gcode.runner import GcodeRunner
from .links.dispenser_sim import SimDispenser
from .links.printer_sim import SimPrinter
from .state import MagnetInsert

log = logging.getLogger("magnet_embed.main_sim")


def _on_sentinel(mi: MagnetInsert) -> None:
    log.info(
        "SENTINEL HIT  X%.3f Y%.3f Z%.3f S%s", mi.pocket_x, mi.pocket_y, mi.seat_z, mi.shear_dir
    )
    log.info("  insert sequence lands in build chunk C2 - continuing the stream")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m magnet_embed.main_sim",
        description="Stream a G-code file through the simulated printer (no hardware).",
    )
    parser.add_argument("gcode", help="path to a .gcode file")
    parser.add_argument("--config", default=None, help="override the config.yaml path")
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

    runner = GcodeRunner(printer, args.gcode, _on_sentinel, config)
    log.info("streaming %s through SimPrinter", args.gcode)
    runner.run()

    st = printer.query_state()
    log.info(
        "done: %d/%d lines sent, %d sentinel(s); final pos X%.2f Y%.2f Z%.2f, nozzle %.0f/%.0f",
        runner.sent_lines,
        runner.total_lines,
        runner.sentinels_seen,
        st.x,
        st.y,
        st.z,
        st.nozzle_temp,
        st.nozzle_target,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
