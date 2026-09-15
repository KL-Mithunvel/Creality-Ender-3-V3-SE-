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
from .exceptions import (
    AckTimeout,
    DispenserError,
    PrinterError,
    ResendRequested,
    SequenceAborted,
)
from .gcode.runner import GcodeRunner
from .links.base import DispenserLink, PrinterLink
from .runlog import RunLog, new_run_log
from .sequences.insert_magnet import insert_magnet
from .state import MagnetInsert

Event = tuple[str, object]  # (kind, payload); kinds: log state prompt done error


class Controller:
    def __init__(
        self,
        printer: PrinterLink,
        dispenser: DispenserLink | None,
        config: dict | None = None,
        *,
        log_dir: str | Path | None = None,
        dispenser_optional: bool = False,
    ) -> None:
        self.printer = printer
        self.dispenser = dispenser
        self.dispenser_optional = dispenser_optional
        self.config = config or load_config()
        self.log_dir = log_dir
        self.gcode_path: Path | None = None
        self.runner: GcodeRunner | None = None

        self._events: "queue.Queue[Event]" = queue.Queue()
        self._answers: "queue.Queue[str]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._runlog: RunLog | None = None
        self._connected = False
        # Guards every printer.command()/query_state() call that can happen
        # concurrently with the run worker's own streaming loop. Shared with
        # `GcodeRunner` (passed in `start_run`) so `set_temp` can safely run
        # mid-print without its request getting interleaved with a streamed
        # line's send/ok handshake.
        self._printer_lock = threading.Lock()
        # True only while `sequences.insert_magnet` is driving the printer
        # directly (unlocked, on the worker thread) - `set_temp` must not run
        # concurrently with that (Dev Rule 6: the sequence owns the heaters
        # during the pause).
        self._in_insert = False

    # --- state -------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def progress(self) -> tuple[int, int]:
        """(current line, total lines) of the active/last run; (0, 0) before any run."""
        r = self.runner
        return (r.current_line, r.total_lines) if r is not None else (0, 0)

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
            try:
                self.dispenser.connect()
            except DispenserError as exc:
                if not self.dispenser_optional:
                    raise
                self._emit(
                    "log",
                    f"dispenser unavailable ({exc}); continuing printer-only - "
                    "magnet inserts will fall back to the operator prompt",
                )
                self.dispenser = None
        self._connected = True
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
        try:
            self.printer.command("G91")
            self.printer.command(f"G1 {axis.upper()}{distance:g} F{feed:g}")
            self.printer.command("G90")
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        self._emit_state()

    def home(self) -> None:
        if self.running:
            self._emit("log", "home ignored - a run is active")
            return
        try:
            self.printer.command("G28")
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        self._emit("log", "homed")
        self._emit_state()

    def set_temp(self, which: str, value: float) -> None:
        """Set the nozzle/bed target. Range-checked; allowed during a normal
        print (locked against the streaming loop) but not while the magnet
        insert sequence owns the heaters."""
        if self._in_insert:
            self._emit(
                "log",
                "temp change ignored - the magnet insert sequence owns the heaters right now",
            )
            return
        lo_key, hi_key = (
            ("nozzle_min_c", "nozzle_max_c") if which == "nozzle" else ("bed_min_c", "bed_max_c")
        )
        lo, hi = self.config["temps"][lo_key], self.config["temps"][hi_key]
        if not lo <= value <= hi:
            self._emit(
                "error",
                f"{which} target {value:g}°C outside the allowed range {lo:g}-{hi:g}°C",
            )
            return
        code = "M104" if which == "nozzle" else "M140"
        with self._printer_lock:
            try:
                self.printer.command(f"{code} S{value:g}")
                state = self.printer.query_state()
            except (PrinterError, AckTimeout, ResendRequested) as exc:
                self._emit("error", f"{type(exc).__name__}: {exc}")
                return
        self._emit("state", state)

    def send_command(self, line: str) -> None:
        """Send one raw G-code line and echo the reply to the log. Idle only."""
        line = line.strip()
        if not line:
            return
        if self.running:
            self._emit("log", f"command ignored - a run is active: {line}")
            return
        self._emit("log", f"> {line}")
        try:
            reply = self.printer.command(line)
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        if reply:
            self._emit("log", f"< {reply}")
        self._emit_state()

    def refresh_state(self) -> None:
        """Poll temps + position. No-op when disconnected or mid-insert; safe to
        call during a normal print (locked against the streaming loop) since it
        only reads (`M105`/`M400`/`M114`), same reasoning as `set_temp`."""
        if not self._connected or self._in_insert:
            return
        with self._printer_lock:
            try:
                self.printer.command("M105")
                state = self.printer.query_state()
            except (PrinterError, AckTimeout, ResendRequested) as exc:
                self._emit("error", f"{type(exc).__name__}: {exc}")
                return
        self._emit("state", state)

    def extrude(self, mm: float, feed: float) -> None:
        """Extrude `mm` at `feed` mm/min (negative `mm` = retract). Idle only."""
        if self.running:
            self._emit("log", "extrude/retract ignored - a run is active")
            return
        try:
            self.printer.command("M83")
            self.printer.command(f"G1 E{mm:g} F{feed:g}")
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        self._emit_state()

    def level_bed(self) -> None:
        """Home, probe a fresh bed mesh (`G29`), enable it (`M420 S1`), and save
        it to EEPROM (`M500`). Idle only - moves the toolhead over the whole bed
        and can take a couple of minutes (blocks like `home()` does; `wait_ok`
        already tolerates a long-running command via Marlin's `busy:` keepalive).

        Exists because the V3 SE's stock firmware ships with
        `RESTORE_LEVELING_AFTER_G28` disabled: `G28` turns mesh compensation
        back off every time, and this printer's Creality Print start G-code
        never sends `M420 S1` to re-enable it - see `.CLAUDE/CLAUDE.md` ->
        Known Technical Debt. Running this before a print gets you a fresh,
        enabled, saved mesh; it does NOT survive the print's own `G28` unless
        the slicer's start G-code (or `GcodeRunner`) re-sends `M420 S1` after it.
        """
        if self.running:
            self._emit("log", "bed leveling ignored - a run is active")
            return
        try:
            self.printer.command("G28")
            self.printer.command("G29")
            self.printer.command("M420 S1")
            self.printer.command("M500")
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        self._emit("log", "bed leveling complete: probed, enabled, saved to EEPROM")
        self._emit_state()

    def start_run(self) -> None:
        if self.running:
            return
        if self.gcode_path is None:
            self._emit("log", "no G-code file loaded")
            return
        if self.log_dir is not None:
            self._runlog = new_run_log(self.log_dir, self.gcode_path.stem)
        self.runner = GcodeRunner(
            self.printer, self.gcode_path, self._on_sentinel, self.config,
            lock=self._printer_lock,
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
        except Exception as exc:  # noqa: BLE001 - surface anything to the UI
            self._emit("error", f"{type(exc).__name__}: {exc}")
        else:
            r = self.runner
            self._emit("done", {"sent": r.sent_lines, "total": r.total_lines,  # type: ignore[union-attr]
                                "sentinels": r.sentinels_seen})
            self._emit_state()
        finally:
            if self._runlog is not None:
                self._runlog.close()
                self._runlog = None

    def _on_sentinel(self, mi: MagnetInsert) -> None:
        self._emit(
            "log",
            f"MAGNET_INSERT X{mi.pocket_x:g} Y{mi.pocket_y:g} Z{mi.seat_z:g} {mi.shear_dir}",
        )
        self._in_insert = True
        try:
            insert_magnet(self.printer, self.dispenser, mi, self.config, self._prompt)
        finally:
            self._in_insert = False
        self._emit("log", "insert sequence complete")
        self._emit_state()

    def _prompt(self, stage: str) -> str:
        self._emit("prompt", stage)
        return self._answers.get()

    # --- helpers -----------------------------------------------

    def _emit(self, kind: str, payload: object = None) -> None:
        self._events.put((kind, payload))
        if self._runlog is not None:
            self._runlog.write(kind, payload)

    def _emit_state(self) -> None:
        self._emit("state", self.printer.query_state())
