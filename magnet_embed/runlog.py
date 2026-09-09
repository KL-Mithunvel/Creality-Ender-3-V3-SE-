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
        self.write("open", f"run log started {datetime.now().isoformat(timespec='seconds')}")

    def write(self, kind: str, payload: object = None) -> None:
        stamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = f"{stamp} {kind}" + (f" {payload}" if payload is not None else "")
        with self._lock:
            if not self._fh.closed:
                self._fh.write(line + "\n")
                self._fh.flush()

    def close(self) -> None:
        with self._lock:
            if not self._fh.closed:
                self.write("close")
                self._fh.close()


def new_run_log(log_dir: str | Path, name_hint: str = "run") -> RunLog:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = "".join(c for c in name_hint if c.isalnum() or c in "-_.")[:40] or "run"
    return RunLog(Path(log_dir) / f"{stamp}-{safe}.log")
