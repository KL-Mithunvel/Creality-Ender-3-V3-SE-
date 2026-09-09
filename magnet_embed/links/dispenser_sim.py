"""Simulated magnet dispenser. Stands in for the Arduino Uno on the dev machine."""

from __future__ import annotations

from ..exceptions import DispenserError
from .base import DispenserLink


class SimDispenser(DispenserLink):
    """Counts dispenses. `fail_on_dispense=True` makes every `dispense()` raise."""

    def __init__(self, *, fail_on_dispense: bool = False) -> None:
        self.connected = False
        self.count = 0
        self.last = "none"
        self._fail = fail_on_dispense

    def connect(self) -> None:
        self.connected = True
        self.last = "connect"

    def disconnect(self) -> None:
        self.connected = False

    def ping(self) -> bool:
        return self.connected

    def dispense(self) -> None:
        if not self.connected:
            raise DispenserError("dispense() before connect()")
        if self._fail:
            raise DispenserError("simulated magazine jam")
        self.count += 1
        self.last = "dispense"

    def reset(self) -> None:
        self.last = "reset"

    def status(self) -> dict:
        return {"servo": 0, "count": self.count, "last": self.last}
