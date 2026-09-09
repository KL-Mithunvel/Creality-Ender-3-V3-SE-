"""Hardware entry point — real printer + real Arduino dispenser.

    python -m magnet_embed.main                 open the control panel on real hardware
    python -m magnet_embed.main --ping          connect to both, report, exit (smoke test)

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


def _build(config):
    p = config["printer"]
    d = config["dispenser"]
    printer = SerialPrinter(
        p["port"], p["baud"],
        ack_timeout_s=p["ack_timeout_s"],
        connect_settle_s=p.get("connect_settle_s", 2.0),
    )
    dispenser = SerialDispenser(
        d["port"], d["baud"], reset_settle_s=d.get("reset_settle_s", 2.5)
    )
    return printer, dispenser


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m magnet_embed.main")
    parser.add_argument("gcode", nargs="?", help="G-code file to pre-load into the panel")
    parser.add_argument("--ping", action="store_true", help="connect to both devices, report, exit")
    parser.add_argument("--config", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(args.config)
    printer, dispenser = _build(config)

    if args.ping:
        rc = 0
        try:
            printer.connect()
            st = printer.query_state()
            print(f"printer OK: X{st.x} Y{st.y} Z{st.z} nozzle {st.nozzle_temp}/{st.nozzle_target}")
            printer.disconnect()
        except (PrinterConnectionError, Exception) as exc:  # noqa: BLE001
            print(f"printer FAIL: {exc}", file=sys.stderr)
            rc = 1
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

    controller = Controller(printer, dispenser, config, log_dir="logs")
    try:
        controller.connect()
    except (PrinterConnectionError, DispenserError) as exc:
        log.error("connect failed: %s", exc)
        return 1
    if args.gcode:
        controller.load_gcode(args.gcode)
    run_gui(controller)
    return 0


if __name__ == "__main__":
    sys.exit(main())
