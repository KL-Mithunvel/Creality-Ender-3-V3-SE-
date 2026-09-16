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

from .config import load_config, save_local_override
from .exceptions import (
    AckTimeout,
    DispenserError,
    PrinterError,
    ResendRequested,
    SequenceAborted,
)
from .gcode.runner import GcodeRunner
from .gcode.toolpath import Toolpath, parse_toolpath
from .links.base import DispenserLink, PrinterLink
from .runlog import RunLog, new_run_log
from .sequences.insert_magnet import insert_magnet
from .state import MagnetInsert

Event = tuple[str, object]  # (kind, payload); kinds: log state prompt done error phase

#: `set_temp`/`refresh_state` wait at most this long for `_printer_lock`
#: (C27) - long enough to ride out the streaming loop's brief per-line hold,
#: short enough that a background one-off command (Home/Level Bed/Z-cal,
#: which can hold the lock for tens of seconds) never visibly freezes the UI.
_LOCK_WAIT_S = 0.3


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
        self.toolpath: Toolpath | None = None
        self.gcode_lines: list[str] = []

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
        # True while the worker is blocked in `_prompt()` waiting for the
        # operator - `emergency_stop` uses it to know whether an "abort"
        # answer is needed to unblock the worker.
        self._prompt_pending = False
        self._estopped = False
        # True while a background one-off command (home/level_bed/
        # start_z_calibration, via `_run_offline`) is in flight - guards every
        # other idle-only action the same way `running` does, since the Tk
        # main thread is free to click something else while these now run.
        self._busy = False

    # --- state -------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    @property
    def busy(self) -> bool:
        """True while a background one-off command (home/level_bed/
        start_z_calibration) is in flight - see `_run_offline`."""
        return self._busy

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def estopped(self) -> bool:
        """True after `emergency_stop()` sent `M112` - the printer needs a
        reset (`M999` or a power-cycle) and a reconnect before anything else."""
        return self._estopped

    @property
    def in_insert(self) -> bool:
        """True while `sequences.insert_magnet` is driving the printer directly
        for the currently paused magnet insert (see `_in_insert`)."""
        return self._in_insert

    @property
    def link_summary(self) -> str:
        """Human-readable description of what `printer`/`dispenser` actually
        are - "simulator" or the real COM port(s) - so the panel's connection
        status is never ambiguous about what it's connected to. `SimPrinter`/
        `SimDispenser` have no `port` attribute; `SerialPrinter`/
        `SerialDispenser` do."""
        printer_port = getattr(self.printer, "port", None)
        if printer_port is None:
            return "simulator"
        bits = [f"printer {printer_port}"]
        if self.dispenser is not None:
            dispenser_port = getattr(self.dispenser, "port", None)
            bits.append(f"dispenser {dispenser_port}" if dispenser_port else "dispenser (sim)")
        return " + ".join(bits)

    @property
    def progress(self) -> tuple[int, int]:
        """(current line, total lines) of the active/last run; (0, 0) before any run."""
        r = self.runner
        return (r.current_line, r.total_lines) if r is not None else (0, 0)

    @property
    def progress_point(self) -> tuple[float, float, float] | None:
        """Nozzle tip position implied by how far the runner has streamed into
        the loaded file, read off the parsed `toolpath` (no extra printer
        traffic - see `Toolpath.progress_position`). `None` if no file with a
        usable toolpath is loaded."""
        if self.toolpath is None:
            return None
        current_line, _ = self.progress
        return self.toolpath.progress_position(current_line)

    @property
    def current_line_text(self) -> str:
        """Raw text of the source line the runner is currently on (1-based,
        matches `progress`). Empty string before/without a loaded file, or
        once past the end of the cached lines."""
        current_line, _ = self.progress
        idx = current_line - 1
        return self.gcode_lines[idx] if 0 <= idx < len(self.gcode_lines) else ""

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
        self._estopped = False
        self._emit("log", "connected")
        self._emit_state()

    def load_gcode(self, path: str | Path) -> None:
        if self.running:
            self._emit("log", "cannot load a file while a run is active")
            return
        self.gcode_path = Path(path)
        try:
            self.toolpath = parse_toolpath(self.gcode_path)
            self.gcode_lines = self.gcode_path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:  # noqa: BLE001 - the live view is best-effort
            self.toolpath = None
            self.gcode_lines = []
            self._emit("log", f"no toolpath preview ({exc})")
        self._emit("log", f"loaded {self.gcode_path.name}")

    def jog(self, axis: str, distance: float) -> None:
        if self.running or self._busy:
            self._emit("log", "jog ignored - busy")
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

    def _run_offline(self, fn) -> None:
        """Run `fn` (which does its own printer calls, inside
        `with self._printer_lock:`) on a daemon thread instead of blocking the
        caller - used for the one-off commands that can take a while (Home,
        Level Bed, start Z-calibration) so the Tk main loop stays responsive.
        `fn` must catch its own printer errors and turn them into `_emit`
        calls; nothing here re-raises."""
        self._busy = True

        def _worker() -> None:
            try:
                fn()
            finally:
                self._busy = False

        threading.Thread(target=_worker, name="offline-command", daemon=True).start()

    def home(self) -> None:
        if self.running or self._busy:
            self._emit("log", "home ignored - busy")
            return

        def _do() -> None:
            with self._printer_lock:
                try:
                    self.printer.command("G28")
                except (PrinterError, AckTimeout, ResendRequested) as exc:
                    self._emit("error", f"{type(exc).__name__}: {exc}")
                    return
            self._emit("log", "homed")
            self._emit_state()

        self._run_offline(_do)

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
        # A short *bounded* wait, not the old unbounded `with self._printer_lock:`
        # - the streaming loop only ever holds the lock for one line (fine to
        # wait out, same as before), but a background one-off command
        # (`_run_offline`) can now hold it for tens of seconds (a G28/G29),
        # and blocking on that would just relocate the "Tk main loop frozen"
        # problem C27 fixed.
        if not self._printer_lock.acquire(timeout=_LOCK_WAIT_S):
            self._emit("log", f"{which} temp change ignored - printer busy, try again")
            return
        try:
            self.printer.command(f"{code} S{value:g}")
            state = self.printer.query_state()
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        finally:
            self._printer_lock.release()
        self._emit("state", state)

    def send_command(self, line: str) -> None:
        """Send one raw G-code line and echo the reply to the log. Idle only."""
        line = line.strip()
        if not line:
            return
        if self.running or self._busy:
            self._emit("log", f"command ignored - busy: {line}")
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
        if not self._connected or self._in_insert or self._estopped:
            return                     # estopped: a halted board would fail every poll
        # Bounded wait, same reasoning as `set_temp`: this fires on a timer,
        # so if a background one-off command is holding the lock for a while,
        # skip this tick rather than freezing the UI to wait it out.
        if not self._printer_lock.acquire(timeout=_LOCK_WAIT_S):
            return
        try:
            self.printer.command("M105")
            state = self.printer.query_state()
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        finally:
            self._printer_lock.release()
        self._emit("state", state)

    def extrude(self, mm: float, feed: float) -> None:
        """Extrude `mm` at `feed` mm/min (negative `mm` = retract). Idle only."""
        if self.running or self._busy:
            self._emit("log", "extrude/retract ignored - busy")
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

        Runs on a background thread (`_run_offline`, C27) so the Tk main loop
        stays responsive for the whole probe - only `_busy`/`running` gate a
        second call, not the caller blocking on this one.
        """
        if self.running or self._busy:
            self._emit("log", "bed leveling ignored - busy")
            return

        def _do() -> None:
            with self._printer_lock:
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

        self._run_offline(_do)

    def start_z_calibration(self) -> None:
        """Home, then travel to `config.zcal.{x,y,start_z}` - the starting point
        for a paper-test Z-offset calibration (see `ui/zcal_dialog.py`). Idle
        only, like `home()`/`level_bed()`; runs on a background thread
        (`_run_offline`, C27) since it starts with a `G28`."""
        if self.running or self._busy:
            self._emit("log", "Z calibration ignored - busy")
            return
        zc = self.config["zcal"]
        feed = self.config["travel"]["feed"]

        def _do() -> None:
            with self._printer_lock:
                try:
                    self.printer.command("G28")
                    self.printer.command(
                        f"G1 X{zc['x']:g} Y{zc['y']:g} Z{zc['start_z']:g} F{feed:g}"
                    )
                except (PrinterError, AckTimeout, ResendRequested) as exc:
                    self._emit("error", f"{type(exc).__name__}: {exc}")
                    return
            self._emit(
                "log",
                f"Z calibration: homed, at X{zc['x']:g} Y{zc['y']:g} Z{zc['start_z']:g} "
                "- nudge down carefully with a sheet of paper under the nozzle",
            )
            self._emit_state()

        self._run_offline(_do)

    def nudge_z(self, delta: float) -> None:
        """Fine relative Z move for Z-offset calibration, at `config.zcal.feed`
        (deliberately slow). Idle only. Stays synchronous (unlike `home`/
        `level_bed`/`start_z_calibration`) - it's a single fast move, not the
        reported "panel freezes" pain point."""
        if self.running or self._busy:
            self._emit("log", "Z nudge ignored - busy")
            return
        feed = self.config["zcal"]["feed"]
        try:
            self.printer.command("G91")
            self.printer.command(f"G1 Z{delta:g} F{feed:g}")
            self.printer.command("G90")
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        self._emit_state()

    def save_z_offset(self, cumulative_delta: float) -> None:
        """Apply `cumulative_delta` (mm nudged since `start_z_calibration`) to
        the trusted `config.zcal.probe_z_offset`, push the result to the
        firmware (`M851` + `M500`), and persist it to `config.local.yaml` -
        same "config is the source of truth" pattern as `magnet_tool_offset`
        (Settings dialog), not a value read back from the printer (the exact
        M851 report text for this firmware fork is unverified - see
        `.CLAUDE/CLAUDE.md` -> Known Technical Debt). Idle only."""
        if self.running or self._busy:
            self._emit("log", "Z offset save ignored - busy")
            return
        new_offset = round(self.config["zcal"]["probe_z_offset"] + cumulative_delta, 3)
        try:
            self.printer.command(f"M851 Z{new_offset:g}")
            self.printer.command("M500")
        except (PrinterError, AckTimeout, ResendRequested) as exc:
            self._emit("error", f"{type(exc).__name__}: {exc}")
            return
        save_local_override({"zcal": {"probe_z_offset": new_offset}})
        self.config["zcal"]["probe_z_offset"] = new_offset
        self._emit(
            "log",
            f"Z offset saved: {new_offset:g} mm (M851 + M500 sent; config.local.yaml updated)",
        )

    def start_run(self) -> None:
        if self.running or self._busy:
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
        """Stop streaming, then leave the printer safe: retract, lift, park,
        and (if `config.cancel.heaters_off`) turn the heaters off. The retreat
        runs on a background thread that waits for the streaming worker to
        actually stop first (Cancel only *signals* the runner - it may still
        be mid-line, or blocked inside an active insert's operator prompt -
        sending new commands before it's really stopped would race
        `GcodeRunner`'s or `insert_magnet`'s own printer calls)."""
        if self.runner is not None:
            self.runner.cancel()
            self._emit("log", "cancelling")
            threading.Thread(
                target=self._safe_cancel_retreat, name="safe-cancel", daemon=True
            ).start()

    def _safe_cancel_retreat(self) -> None:
        worker = self._worker
        if worker is not None:
            worker.join(timeout=self.config["printer"]["ack_timeout_s"] + 5)
            if worker.is_alive():
                self._emit(
                    "log",
                    "cancel: run still finishing (e.g. a magnet insert in progress) "
                    "- safe-cancel retreat skipped; use EMERGENCY STOP if this is urgent",
                )
                return
        if self._estopped or self._in_insert:
            return          # nothing to retreat from / the insert owns the printer
        retract = self.config["retract"]
        park = self.config["park"]
        travel_feed = self.config["travel"]["feed"]
        with self._printer_lock:
            try:
                state = self.printer.query_state()
                safe_z = min(
                    state.z + self.config["park"]["safe_z_lift_mm"],
                    self.config["machine"]["z_max"],
                )
                self.printer.command("M83")
                self.printer.command(f"G1 E-{retract['mm']:g} F{retract['feed']:g}")
                self.printer.command("G90")
                self.printer.command(f"G1 Z{safe_z:g} F{travel_feed:g}")
                self.printer.command(f"G1 X{park['x']:g} Y{park['y']:g} F{travel_feed:g}")
                heaters_off = self.config.get("cancel", {}).get("heaters_off", True)
                if heaters_off:
                    self.printer.command("M104 S0")
                    self.printer.command("M140 S0")
            except (PrinterError, AckTimeout, ResendRequested) as exc:
                self._emit("error", f"safe-cancel retreat failed: {type(exc).__name__}: {exc}")
                return
        suffix = ", heaters off" if heaters_off else " (heaters left as-is)"
        self._emit("log", f"safe-cancel retreat complete: retracted, parked{suffix}")
        self._emit_state()

    def answer_prompt(self, value: str) -> None:
        self._answers.put(value)

    def emergency_stop(self) -> None:
        """Send `M112` (Marlin emergency stop: heaters + steppers off, firmware
        halts until reset) *immediately* - no idle guard, no printer lock, no
        `ok` wait - and stop the run. Allowed at any time, including mid-stream
        and mid-insert; that is the whole point.

        Why no lock: the streaming worker may be holding `_printer_lock`
        inside `wait_ok` for up to `ack_timeout_s`; an emergency stop cannot
        wait for that. Marlin reads `M112` ahead of the command queue when
        `EMERGENCY_PARSER` is enabled (stock V3 SE firmware: unverified - if
        not, it still executes as the next queued command). Any `ok` the
        printer sends for it may be consumed by the worker's in-flight
        `wait_ok`; harmless, since the run is being cancelled anyway.

        After this the printer needs `M999` or a power-cycle, then Connect
        again (`estopped` is cleared by `connect()`).
        """
        if self.runner is not None:
            self.runner.cancel()
        if self._prompt_pending:
            self._answers.put("abort")       # unblock a worker waiting on the operator
        try:
            self.printer.send_line("M112")
        except Exception as exc:  # noqa: BLE001 - an e-stop must never raise out of a button
            self._emit(
                "error",
                f"EMERGENCY STOP: could not send M112 ({type(exc).__name__}: {exc}) - "
                "use the printer's power switch",
            )
            return
        self._estopped = True
        self._emit(
            "error",
            "EMERGENCY STOP sent (M112): printer halted, heaters and motors off. "
            "Power-cycle the printer (or send M999), then Connect again before continuing.",
        )

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
                self._emit("log", self._runlog.summary_text)
                self._runlog = None

    def _on_sentinel(self, mi: MagnetInsert) -> None:
        self._emit(
            "log",
            f"MAGNET_INSERT X{mi.pocket_x:g} Y{mi.pocket_y:g} Z{mi.seat_z:g} {mi.shear_dir}",
        )
        self._in_insert = True
        try:
            insert_magnet(
                self.printer, self.dispenser, mi, self.config, self._prompt,
                toolpath=self.toolpath,      # enables the nozzle-vs-part collision guard
                on_phase=self._on_insert_phase,
            )
        finally:
            self._in_insert = False
        self._emit("log", "insert sequence complete")
        self._emit_state()

    def _on_insert_phase(
        self, phase: str, position: tuple[float, float, float] | None
    ) -> None:
        self._emit("phase", {"phase": phase, "position": position})

    def _prompt(self, stage: str) -> str:
        self._prompt_pending = True
        try:
            self._emit("prompt", stage)
            return self._answers.get()
        finally:
            self._prompt_pending = False

    # --- helpers -----------------------------------------------

    def _emit(self, kind: str, payload: object = None) -> None:
        self._events.put((kind, payload))
        if self._runlog is not None:
            self._runlog.write(kind, payload)

    def _emit_state(self) -> None:
        self._emit("state", self.printer.query_state())
