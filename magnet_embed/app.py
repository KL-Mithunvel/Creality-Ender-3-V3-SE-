"""Controller / mediator between the UI and the printer + dispenser.

No Tkinter here — this class is fully headless and unit-tested. The Tkinter panel
(`magnet_embed.ui.panel`) owns a `Controller`, calls its action methods on the
main thread, and drains `poll_events()` on a timer.

Threading model:
  * `start_run()` spawns a daemon worker that runs `GcodeRunner.run()`.
  * The worker talks to the UI only through `self._events` (a queue).
  * When the insert sequence needs an operator answer, the worker calls
    `_prompt()`, which posts a `("prompt", stage)` event and then blocks on
    `self._answers` until the UI calls `answer_prompt(value)`.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

from .config import load_config
from .exceptions import SequenceAborted
from .gcode.runner import GcodeRunner
from .links.base import DispenserLink, PrinterLink
from .sequences.insert_magnet import insert_magnet
from .state import MagnetInsert

Event = tuple[str, object]  # (kind, payload); kinds: log state prompt done error


class Controller:
    def __init__(
        self,
        printer: PrinterLink,
        dispenser: DispenserLink | None,
        config: dict | None = None,
    ) -> None:
        self.printer = printer
        self.dispenser = dispenser
        self.config = config or load_config()
        self.gcode_path: Path | None = None
        self.runner: GcodeRunner | None = None

        self._events: "queue.Queue[Event]" = queue.Queue()
        self._answers: "queue.Queue[str]" = queue.Queue()
        self._worker: threading.Thread | None = None

    # --- state -------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def poll_events(self) -> list[Event]:
        """Return and clear every event queued since the last call (call from the UI)."""
        out: list[Event] = []
        try:
            while True:
                out.append(self._events.get_nowait())
        except queue.Empty:
            pass
        return out

    # --- actions (call from the UI / main thread) -----------------

    def connect(self) -> None:
        self.printer.connect()
        if self.dispenser is not None:
            self.dispenser.connect()
        self._emit("log", "connected")
        self._emit_state()

    def load_gcode(self, path: str | Path) -> None:
        if self.running:
            self._emit("log", "cannot load a file while a run is active")
            return
        self.gcode_path = Path(path)
        self._emit("log", f"loaded {self.gcode_path.name}")

    def jog(self, axis: str, distance: float) -> None:
        if self.running:
            self._emit("log", "jog ignored - a run is active")
            return
        feed = self.config["travel"]["feed"]
        self.printer.command("G91")
        self.printer.command(f"G1 {axis.upper()}{distance:g} F{feed:g}")
        self.printer.command("G90")
        self._emit_state()

    def home(self) -> None:
        if self.running:
            self._emit("log", "home ignored - a run is active")
            return
        self.printer.command("G28")
        self._emit("log", "homed")
        self._emit_state()

    def set_temp(self, which: str, value: float) -> None:
        if self.running:
            self._emit("log", "temp change ignored - a run is active")
            return
        code = "M104" if which == "nozzle" else "M140"
        self.printer.command(f"{code} S{value:g}")
        self._emit_state()

    def start_run(self) -> None:
        if self.running:
            return
        if self.gcode_path is None:
            self._emit("log", "no G-code file loaded")
            return
        self.runner = GcodeRunner(
            self.printer, self.gcode_path, self._on_sentinel, self.config
        )
        self._worker = threading.Thread(target=self._run, name="gcode-runner", daemon=True)
        self._worker.start()
        self._emit("log", f"run started: {self.gcode_path.name}")

    def pause(self) -> None:
        if self.runner is not None:
            self.runner.pause()
            self._emit("log", "paused")

    def resume(self) -> None:
        if self.runner is not None:
            self.runner.resume()
            self._emit("log", "resumed")

    def cancel(self) -> None:
        if self.runner is not None:
            self.runner.cancel()
            self._emit("log", "cancelling")

    def answer_prompt(self, value: str) -> None:
        self._answers.put(value)

    # --- worker thread ------------------------------------------

    def _run(self) -> None:
        try:
            self.runner.run()  # type: ignore[union-attr]
        except SequenceAborted as exc:
            self._emit("error", f"aborted: {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - surface anything to the UI
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        r = self.runner
        self._emit("done", {"sent": r.sent_lines, "total": r.total_lines,  # type: ignore[union-attr]
                            "sentinels": r.sentinels_seen})
        self._emit_state()

    def _on_sentinel(self, mi: MagnetInsert) -> None:
        self._emit(
            "log",
            f"MAGNET_INSERT X{mi.pocket_x:g} Y{mi.pocket_y:g} Z{mi.seat_z:g} {mi.shear_dir}",
        )
        insert_magnet(self.printer, self.dispenser, mi, self.config, self._prompt)
        self._emit("log", "insert sequence complete")
        self._emit_state()

    def _prompt(self, stage: str) -> str:
        self._emit("prompt", stage)
        return self._answers.get()

    # --- helpers -----------------------------------------------

    def _emit(self, kind: str, payload: object = None) -> None:
        self._events.put((kind, payload))

    def _emit_state(self) -> None:
        self._emit("state", self.printer.query_state())
