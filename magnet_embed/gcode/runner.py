"""Stream a G-code file to a `PrinterLink`, one line at a time, waiting for `ok`.

When a line is the magnet sentinel it is NOT sent to the printer; instead
`on_sentinel(MagnetInsert)` is called synchronously on the run thread (that call
does the park / insert / resume in later chunks).

`run()` is blocking and meant to be driven on a worker thread. `pause()`,
`resume()`, and `cancel()` are safe to call from another thread.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from ..exceptions import SentinelNotFound
from ..links.base import PrinterLink
from ..state import MagnetInsert
from .sentinel import parse_sentinel
from .util import strip_comment

OnSentinel = Callable[[MagnetInsert], None]


class GcodeRunner:
    def __init__(
        self,
        link: PrinterLink,
        gcode_path: str | Path,
        on_sentinel: OnSentinel,
        config: dict,
    ) -> None:
        self.link = link
        self.path = Path(gcode_path)
        self.on_sentinel = on_sentinel
        self._token = config["gcode"]["sentinel_token"]
        self._require_sentinel = bool(config["gcode"].get("require_sentinel", False))
        self._ack_timeout = config["printer"]["ack_timeout_s"]

        self._resume_evt = threading.Event()
        self._resume_evt.set()            # set == running, clear == paused
        self._cancel_evt = threading.Event()

        self.total_lines = 0
        self.sent_lines = 0
        self.current_line = 0
        self.sentinels_seen = 0
        self.finished = False

    # --- control (call from any thread) --------------------------------

    def pause(self) -> None:
        self._resume_evt.clear()

    def resume(self) -> None:
        self._resume_evt.set()

    def cancel(self) -> None:
        self._cancel_evt.set()
        self._resume_evt.set()            # unblock a paused run so it can exit

    @property
    def paused(self) -> bool:
        return not self._resume_evt.is_set()

    @property
    def cancelled(self) -> bool:
        return self._cancel_evt.is_set()

    # --- run (worker thread) -----------------------------------------

    def run(self) -> None:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.total_lines = len(lines)

        for index, raw in enumerate(lines, start=1):
            self.current_line = index
            if self._cancel_evt.is_set():
                self.finished = False
                return
            self._resume_evt.wait()
            if self._cancel_evt.is_set():
                self.finished = False
                return

            line = raw.strip()
            if not line:
                continue

            mi = parse_sentinel(line, self._token)
            if mi is not None:
                self.sentinels_seen += 1
                self.on_sentinel(mi)
                continue

            if not strip_comment(line).strip():
                continue                  # pure comment — don't bother the printer

            self.link.send_line(raw)
            self.link.wait_ok(self._ack_timeout)
            self.sent_lines += 1

        self.finished = True
        if self._require_sentinel and self.sentinels_seen == 0:
            raise SentinelNotFound(
                f"reached end of {self.path} without a {self._token} line"
            )
