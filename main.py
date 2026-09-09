"""Magnet-embedding print assistant — single entry point.

    python main.py                          simulator + GUI  (safe on any machine)
    python main.py --printer  part.gcode    real printer over USB, no dispenser, GUI
    python main.py --hardware               real printer + Arduino dispenser, GUI
    python main.py --hardware --ping        connect to both, report, exit
    python main.py --sim --no-gui part.gcode --confirm success   headless run

Mode is chosen by flag — ``--sim`` (default) / ``--printer`` / ``--hardware`` —
never by code. Ports, baud and timings come from ``magnet_embed/config.yaml``
(machine-specific values in a git-ignored ``config.local.yaml``). Run the
pre-hardware checklist in ``.CLAUDE/CLAUDE.md`` before ``--printer`` / ``--hardware``.
"""

from __future__ import annotations

import argparse
import logging
import sys

from magnet_embed import entry
from magnet_embed.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--sim", dest="mode", action="store_const", const="sim",
                      help="simulated printer + dispenser (default)")
    mode.add_argument("--printer", dest="mode", action="store_const", const="printer",
                      help="real printer over USB, no dispenser")
    mode.add_argument("--hardware", dest="mode", action="store_const", const="hardware",
                      help="real printer + Arduino dispenser")
    parser.set_defaults(mode="sim")

    parser.add_argument("gcode", nargs="?", help="G-code file to pre-load")
    parser.add_argument("--preview", metavar="FILE",
                        help="open the toolpath / insert-motion preview for FILE and exit")
    parser.add_argument("--ping", action="store_true",
                        help="connect to the device(s), report, exit")
    parser.add_argument("--no-gui", action="store_true",
                        help="headless: stream the G-code file and exit (needs a file)")
    parser.add_argument("--no-dispenser", action="store_true",
                        help="--hardware only: don't build the Arduino link")
    parser.add_argument("--confirm", choices=("success", "retry", "abort"), default="success",
                        help="--no-gui: canned answer to the insert prompt (default: success)")
    parser.add_argument("--config", default=None, help="override the config.yaml path")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)

    if args.preview:
        return entry.preview(args.preview, config)

    # sim -> SimDispenser; printer -> always None; hardware -> Uno unless --no-dispenser
    printer, dispenser = entry.build_links(
        args.mode, config, with_dispenser=not args.no_dispenser
    )

    if args.ping:
        return entry.ping(printer, dispenser)

    if args.no_gui:
        if not args.gcode:
            parser.error("--no-gui needs a G-code file")
        return entry.run_headless(printer, dispenser, config, args.gcode, confirm=args.confirm)

    return entry.launch_panel(
        printer, dispenser, config,
        dispenser_optional=(args.mode == "hardware"),
        gcode=args.gcode,
    )


if __name__ == "__main__":
    sys.exit(main())
