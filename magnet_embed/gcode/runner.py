"""Stream a G-code file to a `PrinterLink`, one line at a time, waiting for `ok`.

When a line is the magnet sentinel it is NOT sent to the printer; instead
`on_sentinel(MagnetInsert)` is called synchronously on the run thread (that call
does the park / insert / resume in later chunks).

`run()` is blocking and meant to be driven on a worker thread. `pause()`,
`resume()`, and `cancel()` are safe to call from another thread.

**Line numbers / checksum / resend (C29, opt-in via `config.gcode.
use_line_numbers`, default off).** Plain-line streaming (the verified,
default behavior) has no way to service a `Resend:` — it's fatal. With
numbering on, every line is sent as `N<n> ...*<checksum>` (see
`gcode.util.build_numbered_line`) and a small buffer of recently sent lines
lets a `ResendRequested` be replayed instead of ending the run. Also opt-in
(`config.gcode.resend_leveling_after_home`): re-send `M420 S1` right after
any streamed `G28`, since the stock V3 SE firmware turns bed-mesh
compensation back off on every home (`.CLAUDE/CLAUDE.md` → Known Technical
Debt). Both are unverified on real hardware — bench-test before enabling.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from ..exceptions import ResendRequested, SentinelNotFound
from ..links.base import PrinterLink
from ..state import MagnetInsert
from .sentinel import parse_sentinel
from .util import build_numbered_line, strip_comment

log = logging.getLogger(__name__)

OnSentinel = Callable[[MagnetInsert], None]

#: firmware-pause commands we never forward — the host owns the pause and the
#: insert sequence does the parking (`.CLAUDE/CLAUDE.md` → Key Conventions).
_PAUSE_CODES = ("M0", "M1", "M25", "M600", "M601")

#: how many recently sent numbered lines are kept for a resend replay
_RESEND_BUFFER = 64


class GcodeRunner:
    def __init__(
        self,
        link: PrinterLink,
        gcode_path: str | Path,
        on_sentinel: OnSentinel,
        config: dict,
        lock: threading.Lock | None = None,
    ) -> None:
        self.link = link
        self.path = Path(gcode_path)
        self.on_sentinel = on_sentinel
        self._token = config["gcode"]["sentinel_token"]
        self._require_sentinel = bool(config["gcode"].get("require_sentinel", False))
        self._ack_timeout = config["printer"]["ack_timeout_s"]
        self._use_numbers = bool(config["gcode"].get("use_line_numbers", False))
        self._resend_leveling = bool(config["gcode"].get("resend_leveling_after_home", False))
        self._next_n = 1
        self._sent_buffer: dict[int, str] = {}
        # Shared with `Controller` so an out-of-band command (currently only
        # `set_temp`) can't interleave its send/`ok` with a streamed line's -
        # both would be reading replies off the same serial connection.
        # Defaults to a private lock when run standalone (headless/tests),
        # where nothing else touches `link` concurrently anyway.
        self._lock = lock if lock is not None else threading.Lock()

        self._resume_evt = threading.Event()
        self._resume_evt.set()            # set == running, clear == paused
        self._cancel_evt = threading.Event()

        self.total_lines = 0
        self.sent_lines = 0
        self.current_line = 0
        self.sentinels_seen = 0
        self.pauses_skipped = 0
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

        if self._use_numbers:
            with self._lock:
                self.link.send_line(build_numbered_line(0, "M110 N0"))
                self.link.wait_ok(self._ack_timeout)
            self._next_n = 1

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

            bare = strip_comment(line).strip()
            if not bare:
                continue                  # pure comment — don't bother the printer

            head = bare.split(maxsplit=1)[0].upper()
            if head in _PAUSE_CODES:
                self.pauses_skipped += 1
                log.info(
                    "skipping %s at line %d — the host owns the pause; "
                    "the insert sequence handles parking",
                    head, index,
                )
                continue

            self._transmit(raw, bare)
            self.sent_lines += 1

            if self._resend_leveling and head == "G28":
                log.info(
                    "re-sending M420 S1 after G28 at line %d "
                    "(config.gcode.resend_leveling_after_home)", index,
                )
                self._transmit("M420 S1", "M420 S1")

        self.finished = True
        if self._require_sentinel and self.sentinels_seen == 0:
            raise SentinelNotFound(
                f"reached end of {self.path} without a {self._token} line"
            )

    # --- send (worker thread) -----------------------------------------

    def _transmit(self, raw: str, bare: str) -> None:
        """Send one line, numbered/checksummed and resend-capable if
        `config.gcode.use_line_numbers` is on, plain otherwise (today's
        verified default, unchanged)."""
        if self._use_numbers:
            self._send_numbered(bare)
        else:
            with self._lock:
                self.link.send_line(raw)
                self.link.wait_ok(self._ack_timeout)

    def _send_numbered(self, bare: str) -> None:
        n = self._next_n
        self._next_n += 1
        self._sent_buffer[n] = bare
        if len(self._sent_buffer) > _RESEND_BUFFER:
            del self._sent_buffer[min(self._sent_buffer)]
        with self._lock:
            self._send_and_resolve(n, build_numbered_line(n, bare))

    def _send_and_resolve(self, n: int, text: str) -> None:
        """Send `text` (already numbered) and wait for `ok`; on a resend
        request, replay every buffered line from the requested number through
        the last one sent, in order, recursively handling any further resend
        during that replay. Must be called with `self._lock` already held —
        it is not re-acquired on the recursive path (the lock isn't
        reentrant). Raises `ResendRequested` unchanged if the firmware wants a
        line that's no longer in the buffer (unrecoverable, same as the
        plain-line fatal behavior)."""
        self.link.send_line(text)
        try:
            self.link.wait_ok(self._ack_timeout)
        except ResendRequested as exc:
            from_n = int(exc.line_number)
            for k in range(from_n, self._next_n):
                bare_k = self._sent_buffer.get(k)
                if bare_k is None:
                    raise
                self._send_and_resolve(k, build_numbered_line(k, bare_k))
