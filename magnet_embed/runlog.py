"""Per-run transcript file.

`Controller` writes one `logs/run-<timestamp>.log` per streamed job when it is
given a `log_dir`: a timestamped line for every event it emits (log / state /
prompt / done / error). Handy for after-the-fact debugging of a print.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path


class RunLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()   # close() calls write() while holding it
        self._fh = open(self.path, "w", encoding="utf-8")
        self._start = datetime.now()
        self._done: dict | None = None
        self._errors: list[str] = []
        self._last_state: object | None = None
        #: set by `close()` - a human-readable summary of the run, also
        #: written to the log file after the raw per-event lines.
        self.summary_text: str | None = None
        self.write("open", f"run log started {self._start.isoformat(timespec='seconds')}")

    def write(self, kind: str, payload: object = None) -> None:
        if kind == "error":
            self._errors.append(str(payload))
        elif kind == "done" and isinstance(payload, dict):
            self._done = payload
        elif kind == "state":
            self._last_state = payload

        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"{stamp} {kind}" + (f" {payload}" if payload is not None else "")
        with self._lock:
            if not self._fh.closed:
                self._fh.write(line + "\n")
                self._fh.flush()

    def close(self) -> None:
        with self._lock:
            if not self._fh.closed:
                self.summary_text = self._build_summary()
                self.write("close")
                self._fh.write(self.summary_text + "\n")
                self._fh.flush()
                self._fh.close()

    def _build_summary(self) -> str:
        duration = datetime.now() - self._start
        lines = ["=== SUMMARY ===", f"duration: {duration}"]
        if self._done is not None:
            sent = self._done.get("sent", "?")
            total = self._done.get("total", "?")
            sentinels = self._done.get("sentinels", "?")
            lines.append(f"lines sent: {sent}/{total}")
            lines.append(f"magnet inserts (sentinels) seen: {sentinels}")
        else:
            lines.append("run did not reach completion (cancelled, or an error below)")
        if self._errors:
            lines.append(f"errors ({len(self._errors)}):")
            lines.extend(f"  - {e}" for e in self._errors)
        else:
            lines.append("errors: none")
        st = self._last_state
        if st is not None:
            lines.append(
                f"final position: X{st.x:.1f} Y{st.y:.1f} Z{st.z:.2f}"
            )
            lines.append(
                f"final temps: nozzle {st.nozzle_temp:.0f}/{st.nozzle_target:.0f}  "
                f"bed {st.bed_temp:.0f}/{st.bed_target:.0f}"
            )
        lines.append("=== END SUMMARY ===")
        return "\n".join(lines)


def new_run_log(log_dir: str | Path, name_hint: str = "run") -> RunLog:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(c for c in name_hint if c.isalnum() or c in "-_.")[:40] or "run"
    return RunLog(Path(log_dir) / f"{stamp}-{safe}.log")
