"""Simulation entry point — no hardware.

Prefer ``python main.py`` (sim is the default mode) at the repo root. Kept as
``python -m magnet_embed.main_sim`` for back-compat; thin-wraps `magnet_embed.entry`.

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

from . import entry
from .config import load_config


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
        printer, dispenser = entry.build_links("sim", config, command_delay=0.03)
        return entry.launch_panel(
            printer, dispenser, config, dispenser_optional=False, gcode=args.gcode
        )

    if not args.gcode:
        parser.error("a .gcode file is required unless --gui is given")
    printer, dispenser = entry.build_links("sim", config, command_delay=0.0)
    return entry.run_headless(printer, dispenser, config, args.gcode, confirm=args.confirm)


if __name__ == "__main__":
    sys.exit(main())
