"""Abstract interfaces for the printer and dispenser links.

Real and simulated implementations raise the *same* exception types
(`magnet_embed.exceptions`) so calling code cannot tell them apart.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..state import PrinterState


class PrinterLink(ABC):
    """A connection that consumes G-code lines and acknowledges each with `ok`.

    Implementations: `printer_sim.SimPrinter` (dev machine) and, from C5,
    `printer_serial.SerialPrinter` (real Ender-3 V3 SE over USB-C).
    """

    @abstractmethod
    def connect(self) -> None:
        """Open the connection and handshake. Raises `PrinterConnectionError`."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection. Safe to call when already disconnected."""

    @abstractmethod
    def send_line(self, line: str) -> None:
        """Send one G-code line to the printer. Does not wait for `ok`."""

    @abstractmethod
    def wait_ok(self, timeout_s: float | None = None) -> str:
        """Block until the printer acknowledges the last line; return the ok payload.

        Raises `AckTimeout`, `PrinterError`, or `ResendRequested`.
        """

    @abstractmethod
    def query_state(self) -> PrinterState:
        """Return a best-effort snapshot of position / temps / modal state."""

    def command(self, line: str, timeout_s: float | None = None) -> str:
        """Convenience: `send_line` then `wait_ok`."""
        self.send_line(line)
        return self.wait_ok(timeout_s)


class DispenserLink(ABC):
    """The Arduino Uno that dispenses one magnet onto the holding pole per call."""

    @abstractmethod
    def connect(self) -> None:
        """Open the connection (riding out the Uno auto-reset for the real link)."""

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @abstractmethod
    def ping(self) -> bool:
        """`PING` -> `PONG`. Return True if the MCU answered."""

    @abstractmethod
    def dispense(self) -> None:
        """Feed exactly one magnet to the holding pole. Raises `DispenserError`."""

    @abstractmethod
    def reset(self) -> None:
        """Return the servo to its home / loaded position."""

    @abstractmethod
    def status(self) -> dict:
        """Return `{'servo': int, 'count': int, 'last': str}`."""
