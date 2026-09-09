"""Full-hardware entry point — real printer + real Arduino dispenser.

Prefer ``python main.py --hardware`` at the repo root. This module stays as
``python -m magnet_embed.main`` for back-compat and thin-wraps `magnet_embed.entry`.

    python -m magnet_embed.main                 open the control panel on real hardware
    python -m magnet_embed.main --ping          connect to both, report, exit
    python -m magnet_embed.main --no-dispenser  printer only, don't build the Uno link

The Uno is optional at runtime: without ``--no-dispenser`` the dispenser link is
built, but if it can't connect the app logs a warning and runs printer-only for
the session (a magnet sentinel then falls back to the operator "Load a magnet"
prompt). COM ports and timings come from `magnet_embed/config.yaml`.
"""

from __future__ import annotations

import sys

if __package__ in (None, ""):  # run as a bare script (e.g. from an IDE), not `python -m`
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import logging

from magnet_embed import entry
from magnet_embed.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m magnet_embed.main")
    parser.add_argument("gcode", nargs="?", help="G-code file to pre-load into the panel")
    parser.add_argument("--ping", action="store_true", help="connect to the device(s), report, exit")
    parser.add_argument(
        "--no-dispenser", action="store_true",
        help="printer only: don't build the Arduino dispenser link",
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)
    printer, dispenser = entry.build_links(
        "hardware", config, with_dispenser=not args.no_dispenser
    )

    if args.ping:
        return entry.ping(printer, dispenser)
    return entry.launch_panel(
        printer, dispenser, config, dispenser_optional=True, gcode=args.gcode
    )


if __name__ == "__main__":
    sys.exit(main())
