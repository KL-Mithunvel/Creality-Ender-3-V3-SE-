"""Real dispenser link — newline ASCII to the Arduino Uno magazine servo.

Protocol (see `.CLAUDE/CLAUDE.md` -> Key Conventions):
    host -> Uno : PING | DISPENSE | RESET | STATUS
    Uno  -> host: PONG | OK DISPENSE | OK RESET | STATUS servo=.. count=.. last=..
                  ERR DISPENSE <reason> | WARN IDLE

Opening the port resets the Uno (~2 s bootloader); `connect()` waits it out and
then PINGs until it gets PONG.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from ..config import load_config
from ..exceptions import DispenserError
from .base import DispenserLink

log = logging.getLogger(__name__)


class SerialDispenser(DispenserLink):
    def __init__(
        self,
        port: str,
        baud: int = 115200,
        *,
        reset_settle_s: float = 2.5,
        reply_timeout_s: float = 5.0,
        ping_timeout_s: float = 1.0,
        read_timeout_s: float = 0.5,
        transport_factory=None,
    ) -> None:
        self.port = port
        self.baud = baud
        self._settle = reset_settle_s
        self._reply_timeout = reply_timeout_s
        self._ping_timeout = ping_timeout_s
        self._read_timeout = read_timeout_s
        self._make_transport = transport_factory or self._default_transport
        self._ser = None
        self.connected = False

    def _default_transport(self):
        import serial

        return serial.Serial(self.port, self.baud, timeout=self._read_timeout)

    # --- DispenserLink -----------------------------------------

    def connect(self) -> None:
        try:
            self._ser = self._make_transport()
        except Exception as exc:  # noqa: BLE001
            raise DispenserError(f"cannot open {self.port}: {exc}") from exc
        time.sleep(self._settle)
        _safe(self._ser.reset_input_buffer)
        for _ in range(5):
            if self.ping():
                self.connected = True
                log.info("dispenser up on %s", self.port)
                return
        raise DispenserError(f"no PONG from the Uno on {self.port}")

    def disconnect(self) -> None:
        if self._ser is not None:
            _safe(self._ser.close)
        self.connected = False

    def ping(self) -> bool:
        try:
            self._cmd("PING", "PONG", timeout=self._ping_timeout)
            return True
        except DispenserError:
            return False

    def dispense(self) -> None:
        self._cmd("DISPENSE", "OK DISPENSE")

    def reset(self) -> None:
        self._cmd("RESET", "OK RESET")

    def status(self) -> dict:
        line = self._cmd("STATUS", "STATUS")
        fields: dict = {}
        for token in line.split()[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key] = value
        return fields

    # --- internals ---------------------------------------------

    def _cmd(self, command: str, expect_prefix: str, timeout: float | None = None) -> str:
        if self._ser is None:
            raise DispenserError(f"{command}: not connected")
        self._ser.write((command + "\n").encode("ascii", "replace"))
        deadline = time.monotonic() + (timeout or self._reply_timeout)
        while time.monotonic() < deadline:
            raw = self._ser.readline()
            if not raw:
                continue
            line = raw.decode("ascii", "replace").strip()
            if not line:
                continue
            if line.startswith("ERR"):
                raise DispenserError(line)
            if line.startswith(expect_prefix):
                return line
            # ignore boot banner / WARN IDLE / stray lines
        raise DispenserError(f"{command}: no '{expect_prefix}' within {timeout or self._reply_timeout:g}s")


def _safe(fn) -> None:
    try:
        fn()
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m magnet_embed.links.dispenser_serial")
    parser.add_argument("--ping", action="store_true")
    parser.add_argument("--dispense", action="store_true", help="connect and dispense one magnet")
    parser.add_argument("--port", default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = load_config()["dispenser"]
    port = args.port or cfg["port"]
    d = SerialDispenser(port, cfg["baud"], reset_settle_s=cfg.get("reset_settle_s", 2.5))
    try:
        d.connect()
        if args.dispense:
            d.dispense()
            print("OK: dispensed one magnet")
        else:
            print(f"OK: {port} answered PONG; status {d.status()}")
    except DispenserError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        d.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
