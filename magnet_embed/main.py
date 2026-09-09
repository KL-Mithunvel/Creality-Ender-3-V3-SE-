"""Hardware entry point — real printer + real Arduino dispenser.

    python -m magnet_embed.main                 open the control panel on real hardware
    python -m magnet_embed.main --ping          connect to both, report, exit (smoke test)
    python -m magnet_embed.main --no-dispenser  printer only, don't build the Uno link

The Uno is optional at runtime: without ``--no-dispenser`` the dispenser link is
built, but if it can't connect (Uno not wired yet) the app logs a warning and runs
printer-only for that session — a magnet sentinel then falls back to the operator
"Load a magnet" prompt. Use ``main_printer`` if you never want the dispenser.

COM ports and timings come from `magnet_embed/config.yaml` (override machine-specific
values in `config.local.yaml`). Run the pre-hardware checklist in `.CLAUDE/CLAUDE.md`
before using this.
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import load_config
from .exceptions import DispenserError, PrinterConnectionError
from .links.dispenser_serial import SerialDispenser
from .links.printer_serial import SerialPrinter

log = logging.getLogger("magnet_embed.main")


def _build(config, *, with_dispenser: bool = True):
    p = config["printer"]
    printer = SerialPrinter(
        p["port"], p["baud"],
        ack_timeout_s=p["ack_timeout_s"],
        connect_settle_s=p.get("connect_settle_s", 2.0),
    )
    dispenser = None
    if with_dispenser:
        d = config["dispenser"]
        dispenser = SerialDispenser(
            d["port"], d["baud"], reset_settle_s=d.get("reset_settle_s", 2.5)
        )
    return printer, dispenser


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
    printer, dispenser = _build(config, with_dispenser=not args.no_dispenser)

    if args.ping:
        rc = 0
        try:
            printer.connect()
            st = printer.query_state()
            print(f"printer OK: X{st.x} Y{st.y} Z{st.z} nozzle {st.nozzle_temp}/{st.nozzle_target}")
            printer.disconnect()
        except Exception as exc:  # noqa: BLE001 - report any failure and exit non-zero
            print(f"printer FAIL: {exc}", file=sys.stderr)
            rc = 1
        if dispenser is None:
            print("dispenser SKIPPED: --no-dispenser")
        else:
            try:
                dispenser.connect()
                print(f"dispenser OK: status {dispenser.status()}")
                dispenser.disconnect()
            except DispenserError as exc:
                print(f"dispenser FAIL: {exc}", file=sys.stderr)
                rc = 1
        return rc

    from .app import Controller
    from .ui.panel import run_gui

    controller = Controller(
        printer, dispenser, config, log_dir="logs", dispenser_optional=True
    )
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
