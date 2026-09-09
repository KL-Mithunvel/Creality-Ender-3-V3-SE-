"""Printer-only entry point — real printer, no Arduino dispenser.

    python -m magnet_embed.main_printer                 open the control panel (printer only)
    python -m magnet_embed.main_printer part.gcode      ... and pre-load a G-code file
    python -m magnet_embed.main_printer --ping          connect to the printer, report, exit

Use this to stream a real print, jog, send raw G-code and load filament while the
Arduino dispenser / applicator are not attached. It wires only the real
`SerialPrinter`; the `Controller` runs with `dispenser=None`. If a streamed file
contains a `;MAGNET_INSERT` sentinel, the panel's "Load a magnet" operator prompt
is the fallback (same as Phase 1 with no dispenser).

COM ports and timings come from `magnet_embed/config.yaml` (override machine-specific
values in `config.local.yaml`). Simulation is a *separate* entry point
(`python -m magnet_embed.main_sim`), never a flag here.
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .exceptions import PrinterConnectionError
from .links.printer_serial import SerialPrinter

log = logging.getLogger("magnet_embed.main_printer")


def _build(config) -> SerialPrinter:
    p = config["printer"]
    return SerialPrinter(
        p["port"], p["baud"],
        ack_timeout_s=p["ack_timeout_s"],
        connect_settle_s=p.get("connect_settle_s", 2.0),
    )


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
    printer = _build(config)

    if args.ping:
        try:
            printer.connect()
            st = printer.query_state()
            print(f"printer OK: X{st.x} Y{st.y} Z{st.z} nozzle {st.nozzle_temp}/{st.nozzle_target}")
            printer.disconnect()
        except Exception as exc:  # noqa: BLE001 - report any failure and exit non-zero
            print(f"printer FAIL: {exc}", file=sys.stderr)
            return 1
        return 0

    from .app import Controller
    from .ui.panel import run_gui

    controller = Controller(printer, None, config, log_dir="logs")
    try:
        controller.connect()
    except PrinterConnectionError as exc:
        log.error("connect failed: %s", exc)
        return 1
    if args.gcode:
        controller.load_gcode(args.gcode)
    run_gui(controller)
    return 0


if __name__ == "__main__":
    sys.exit(main())
