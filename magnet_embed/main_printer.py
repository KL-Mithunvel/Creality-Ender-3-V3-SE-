"""Printer-only entry point — real printer, no dispenser.

Prefer ``python main.py --printer`` at the repo root. Kept as
``python -m magnet_embed.main_printer`` for back-compat; thin-wraps `magnet_embed.entry`.

    python -m magnet_embed.main_printer --ping        connect to the printer, report, exit
    python -m magnet_embed.main_printer part.gcode    control panel, file pre-loaded

Stream a print, jog, send raw G-code, or load filament with no Uno attached.
A ``;MAGNET_INSERT`` sentinel falls back to the operator "Load a magnet" prompt.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import entry
from .config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m magnet_embed.main_printer")
    parser.add_argument("gcode", nargs="?", help="G-code file to pre-load into the panel")
    parser.add_argument("--ping", action="store_true", help="connect to the printer, report, exit")
    parser.add_argument("--config", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)
    printer, dispenser = entry.build_links("printer", config)

    if args.ping:
        return entry.ping(printer, dispenser)
    return entry.launch_panel(
        printer, dispenser, config, dispenser_optional=False, gcode=args.gcode
    )


if __name__ == "__main__":
    sys.exit(main())
