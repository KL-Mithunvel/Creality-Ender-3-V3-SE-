# Software Build Plan — Printer Control

Chunk-by-chunk implementation plan for the host software. Sits under
`project/PROJECT_PLAN.md` (which owns the overall Phase 0–3 roadmap); this file
breaks **Phase 1** (and the structural half of Phase 2) into buildable, testable
chunks. Each chunk: build → `pytest` green → stage → commit.

| | |
|--|--|
| Owner | kl mithunvel |
| Created | 2026-09-09 |
| Status | **C1–C8 + Phase 1.6 (C13–C19) + C20 + C21 + C22 + C23 + C24 + C25 (collision guard + Emergency Stop) done — 245 tests.** One root `python main.py` (mode by flag, opens maximized), bring-your-own-G-code, toolpath + insert-motion preview, "Plan magnet insert…" dialog (now with an embedded live preview of the insert motion), a two-column panel (jog/temperature/filament on the left, the live-print view + send-G-code + log on the right, both stretching to fill a maximized window) with a mode/port indicator, an embedded live-print view (2D current-layer + isometric 3D shown side by side, with a Global-bed/Local-part crop toggle and tight equal-scale axes — a path that grows as the nozzle passes through it — plus a nozzle marker and current-step G-code text) during a run, and a guided Z-offset calibration dialog. Magnet-flow hardware smoke test still pending the applicator build; the Z-calibration workflow is itself untested on real hardware — see Known Technical Debt. |
| Overall plan | `project/PROJECT_PLAN.md` |
| Architecture / rules | `.CLAUDE/CLAUDE.md` |

---

## Ground rules (from `.CLAUDE/CLAUDE.md` + `CLAUDE-COMMON.md`)

- **Sim first.** Every chunk runs against `SimPrinter` / `SimDispenser` on the dev
  machine. No chunk depends on real hardware to be tested.
- **One commit per chunk**, docs updated in the same commit.
- **No hardcoded ports / coords / temps** — all from `magnet_embed/config.yaml`.
- **venv active** for every Python command; deps pinned in `requirements.txt`.
- Tests in `tests/`, `pytest`. Cover the happy path + the key failure modes.

---

## Protocol notes (research — see References)

Host-controlled streaming to Marlin over USB serial:

- **Flow control:** send one command, wait for a line starting with `ok`, then send
  the next. This is Printrun's `clear` flag. No line numbers / checksums for the
  prototype (plain lines) — add `M110` + checksum only if the printer requests resends.
- **Lines the receiver must handle:**
  | Line | Meaning | Action |
  |------|---------|--------|
  | `ok` / `ok T:210 /210 B:60 …` | command accepted | clear to send next; parse temps if present |
  | `wait` | printer idle, nothing queued | heartbeat — keep waiting, not an error |
  | `busy: processing` / `echo:busy: processing` | long command running | reset the ack timeout, keep waiting |
  | `echo:busy: paused for user` | `M0`/`M1` wait | we don't send `M0`; surface if seen |
  | `Resend: N` / `rs N` | firmware wants line N | prototype: raise `ResendRequested` (we send plain lines) |
  | `Error:<msg>` | firmware error | raise `PrinterError` with the message |
  | `//action:<x>` | host action command | parse if present (Creality stock likely has it off) |
  | `start`, `Marlin x.x.x`, `echo:` caps | boot banner | discard during connect settle |
- **`ok` ≠ motion complete.** Marlin returns `ok` when a move enters the planner
  buffer. To know motion finished, send `M400` (it withholds `ok` until the queue
  drains). The insert sequence gates every phase transition with `M400`.
- **Useful M-codes:** `M115` (firmware info — liveness probe), `M114` (position;
  send `M400` first), `M105` (temp), `M155 S<seconds>` (auto temp reports),
  `M104/M109` (nozzle set / set+wait), `M140/M190` (bed), `G92` (set position),
  `M82/M83` (extruder absolute/relative), `G90/G91` (positioning mode).
- **Connect settle:** open port at 115200, `dtr=False` first (some Creality boards
  reset on connect like an Arduino), wait ~2 s, drain the banner, send `M115`,
  wait for `ok`. Only then "connected".
- **Ender 3 V3 SE:** stock firmware has documented OctoPrint/serial friction
  (`M110`, host action commands). Plain-line streaming avoids `M110`. Keep the
  receive parser liberal; test the real link on the bench early (C5).

---

## Chunks

### C1 — Skeleton: config, sim printer, sentinel, runner (headless)  ✅ *(commit after this section)*

**Goal.** A runnable headless pipeline: load a `.gcode`, stream it through
`SimPrinter`, detect the sentinel, log progress. Plus the structural interfaces
everything else hangs off.

**Done:** all files below created; 33 tests pass; `python -m magnet_embed.main_sim
tests/data/sample.gcode` streams 18/25 lines (7 comments skipped) and logs one
`SENTINEL HIT`. Deviations from the sketch: comment/word helpers live in
`gcode/util.py` (shared by sim + runner); `PrinterLink`/`DispenserLink` are both in
`links/base.py`; `requirements-dev.txt` split from `requirements.txt`; `config.py`
does light required-key validation now (the C6 item is a fuller schema check).

**Files**
```
requirements.txt              pyyaml, pyserial, pytest
pyproject.toml                pytest config, metadata, py>=3.12
magnet_embed/
  __init__.py
  config.py                   load_config(path=None) -> dict  (config.yaml + optional config.local.yaml deep-merge)
  config.yaml                  committed defaults (ports, park, temps, offset, press.*, shear.*, limits, sentinel_token)
  state.py                    PrinterState, MagnetInsert  (dataclasses)
  exceptions.py               PrinterConnectionError, AckTimeout, PrinterError, ResendRequested,
                              SentinelParseError, SentinelNotFound, DispenserError, OutOfEnvelopeError
  links/
    __init__.py
    base.py                   PrinterLink (ABC), DispenserLink (ABC)
    printer_sim.py            SimPrinter(PrinterLink) — parse G0/G1/G28/G90/G91/G92/M82/M83/
                              M104/M109/M140/M190/M114/M115/M400/M105; track XYZE + temps +
                              modal state; instant "ok"; keep a .sent log + .moves log
    dispenser_sim.py         SimDispenser(DispenserLink) — ping/dispense/reset/status, counts dispenses
  gcode/
    __init__.py
    sentinel.py              parse_sentinel(line, token) -> MagnetInsert | None  (raises SentinelParseError)
    runner.py                GcodeRunner(link, path, on_sentinel, config) — .run()/.pause()/.resume()/.cancel(),
                              threading.Event gating, line-count progress, on_sentinel callback
  sequences/
    __init__.py
    insert_magnet.py         SIGNATURE + SAVE..RESUME docstring + raise NotImplementedError  (filled in C2)
  main_sim.py                 CLI: python -m magnet_embed.main_sim <file.gcode> — wires sims, runs, logs
tests/
  __init__.py  conftest.py
  data/sample.gcode           ~25 lines: ;LAYER: markers, moves, one ;MAGNET_INSERT line
  test_config.py  test_sentinel.py  test_printer_sim.py  test_runner.py
```

**Not in C1:** real serial, postprocess, insert-sequence body, Tkinter UI, `.ino`.

**Tests / acceptance**
- `pytest` green.
- `parse_sentinel` — valid line → correct `MagnetInsert`; no token → `None`;
  malformed (`S+Q`, missing `Z`) → `SentinelParseError`.
- `SimPrinter` — `G90`/`G1 X10` → x==10; `G91` relative; `M83` relative E; `M109 S200`
  → temp target/current == 200; `G92 X0` resets; unknown line still `ok`.
- `GcodeRunner` — every non-sentinel line reaches `SimPrinter.sent`; sentinel line
  **not** sent; `on_sentinel` called once with parsed fields; `pause()` halts progress;
  `cancel()` stops the run.
- `python -m magnet_embed.main_sim tests/data/sample.gcode` prints progress and one
  `SENTINEL HIT X.. Y.. Z.. S..` line.

---

### C2 — Insert-magnet state machine (against the sim)  ✅

**Goal.** Fill in `sequences/insert_magnet.py` — the full `SAVE → PARK → DISPENSE →
APPROACH → PRESS → SHEAR → LIFT → ASK → RESUME` machine, driven by `MagnetInsert`
+ config, gated by `M400`, verified against `SimPrinter`.

**Done:** `sequences/insert_magnet.py` implemented (44 tests total, 11 new).
Decisions/deviations: `prompt(stage)` takes a stage arg (`"dispense"` /
`"confirm"`) instead of a no-arg callable; offset convention fixed to
`(pole − nozzle)` so press Z is `seat_z − offset.z`; move helpers kept inline
(`_send`, `_fmt`) rather than a `moves.py` module; `config.yaml` gained `travel`,
`sequence`, and `retract`/`prime` are now required keys; `SimPrinter._move` no
longer logs a "move" for feedrate-only `G1 F…` lines; `main_sim` runs the real
sequence with a `--confirm` canned answer.

**Files:** `sequences/insert_magnet.py`, `gcode/moves.py` (small G-code builders:
`travel`, `z_hop`, `retract`, `set_temp`, `wait_moves`), `sequences/envelope.py`
(in-range check), wire `on_sentinel` in `main_sim.py`, tests.

**Tests / acceptance**
- Park before any XY travel; nozzle set to `standby_nozzle_temp_c`.
- `dispenser.dispense()` called once (or the prompt, if no dispenser).
- APPROACH target == `pocket_xy − magnet_tool_offset.xy`; PRESS Z ==
  `seat_z − magnet_tool_offset.z` (offset = pole tip − nozzle tip; corrected in
  C2); SHEAR == lateral `shear.distance` along `shear_dir`.
- RESUME returns X/Y/Z to the saved values, restores `G90`/`M82`/feedrate, un-retracts.
- Out-of-envelope target → `OutOfEnvelopeError`, no motion commanded, print still paused.
- `prompt` returns `"retry"` → machine re-runs from DISPENSE; `"abort"` → heaters
  safed, `SequenceAborted` raised, printer resumable.
- Any injected fault mid-sequence → temp restored, no partial move left pending, re-raised.
- **No `G28` emitted anywhere** (assert against `SimPrinter.sent`).

---

### C3 — G-code post-processor  ✅

**Goal.** `gcode/postprocess.py` + CLI — inject `;MAGNET_INSERT X Y Z S<dir>` at a
layer or Z height.

**Done:** `gcode/postprocess.py` + CLI; `_detect_layers` handles Cura `;LAYER:<n>`
(height from the first Z move) and PrusaSlicer `;LAYER_CHANGE`+`;Z:`; sentinel goes
right after the marker block; `PostprocessError` for no-markers / missing layer /
height-above-top. `fmt_number` moved to `gcode/util.py` (shared with
`insert_magnet`). Fixtures `tests/data/cura_sample.gcode` + `prusa_sample.gcode`;
12 new tests (56 total).

**Files:** `gcode/postprocess.py`, `tests/data/cura_sample.gcode`,
`tests/data/prusa_sample.gcode`, `test_postprocess.py`.

**Tests / acceptance**
- Cura / Creality Print (`;LAYER:<n>`) and PrusaSlicer (`;LAYER_CHANGE` + `;Z:`) markers.
- `--layer N` inserts before that layer's first move; `--z H` picks the first layer ≥ H.
- Exactly one sentinel inserted; original lines otherwise untouched; file still parses.
- `--shear` validates against `{+X,-X,+Y,-Y}`; bad value → non-zero exit + message.
- Round-trip: `parse_sentinel` reads back what `postprocess` wrote.

---

### C4 — Tkinter control panel + threading  ✅

**Goal.** `ui/panel.py` + an `app.py` mediator: streaming on a worker thread, UI on
the main thread, `queue.Queue` + `root.after()` for updates. Success/Retry/Abort modal.
Jog/home enabled only when not printing.

**Done:** `app.Controller` — headless mediator (worker thread runs `GcodeRunner`;
worker→UI via an events queue; UI→worker prompt answers via an answers queue on
which `_prompt` blocks). `ui/panel.py` — `ControlPanel` (connect / load / run /
pause / resume / cancel / jog+home idle-only / temps / read-only log) + a modal
`Success/Retry/Abort` (and `Ready/Abort`) dialog; `run_gui()`. `SimPrinter` gained
`command_delay` so runs take real time for the GUI + threading tests. `main_sim`
gained `--gui`. `test_app.py` — 8 tests (full run, abort, pause/resume, cancel,
jog gating, load gating). 64 tests total. UI defaults as announced (jog 0.1/1/10,
modal prompt, no raw G-code box).

**Files:** `magnet_embed/ui/panel.py`, `magnet_embed/app.py`, update `main_sim.py` to
launch the GUI, `tests/test_app.py` (mediator logic only, not widgets).

**Tests / acceptance**
- Mediator: run/pause/resume/cancel drive `GcodeRunner` correctly.
- `on_sentinel` posts a prompt request to the UI queue and blocks the worker until answered.
- Jog commands rejected while a run is active.
- Manual: `python -m magnet_embed.main_sim --gui tests/data/sample.gcode` — panel opens,
  streams, prompts at the sentinel, resumes, completes.

---

### C5 — Real serial links  ✅

**Goal.** `links/printer_serial.py` and `links/dispenser_serial.py`, plus a
receive-line parser proven against synthetic firmware output.

**Done:** `links/_marlin_rx.py` (`classify`, `parse_temps`, `parse_position`);
`SerialPrinter` (`dtr=False` pre-open, `M115` handshake tolerating the banner,
`wait_ok` resets its deadline on `busy:` and skips `wait`, `Resend:`→
`ResendRequested`, `Error:`→`PrinterError`; modes+feed tracked from the outgoing
stream, temps+position absorbed from `ok`/`M114`; `query_state()` issues
`M400`+`M114`); `SerialDispenser` (rides the ~2 s Uno reset, PINGs to `PONG`,
`DISPENSE`/`RESET`/`STATUS`, `ERR…`→`DispenserError`). Each link module has a
`--ping` CLI; `magnet_embed/main.py` is the hardware entry point (`--ping` smoke
test, else the panel on real links). Tested with an injected `FakeSerial`
transport — no pyserial needed in the tests. 27 new tests (91 total). **Hardware
smoke test on the actual printer is still a manual step** (`.CLAUDE/CLAUDE.md` →
Deployment Notes).

**Files:** `magnet_embed/links/printer_serial.py`, `magnet_embed/links/dispenser_serial.py`,
`magnet_embed/links/_marlin_rx.py` (line classifier), fault-injection knobs in
`SimPrinter`, `test_marlin_rx.py`, `test_dispenser_serial.py`, `main.py` (hardware entry).

**Tests / acceptance**
- `_marlin_rx.classify()` maps `ok` / `ok T:…` / `wait` / `busy: processing` /
  `Resend: 5` / `Error:x` / `echo:x` / `//action:paused` / banner lines correctly.
- `printer_serial`: `dtr=False` pre-open; connect drains banner then `M115`→`ok`;
  ack wait resets on `busy`; `AckTimeout` after `config.printer.ack_timeout_s` of silence
  (no `busy`/`wait`); `Resend:` → `ResendRequested`.
- `dispenser_serial`: rides out the ~2 s Uno reset; `PING`→`PONG`; `ERR DISPENSE x`
  → `DispenserError`.
- CLIs: `python -m magnet_embed.links.printer_serial --ping`,
  `… dispenser_serial --ping`.
- **Hardware smoke test is a documented manual step** (`.CLAUDE/CLAUDE.md` →
  Deployment Notes), not automated.

---

### C6 — Integration + full sanity pass  ✅

**Goal.** One end-to-end sim test, run logging, config validation, and a full review.

**Done:** `magnet_embed/runlog.py` (`RunLog` — per-run `logs/<ts>-<name>.log`, wired
into `Controller` via `log_dir=`; `main` + `main_sim --gui` opt in). `config._validate`
extended with numeric-type and sentinel-token checks. `tests/test_integration_sim.py`
(full run + abort, asserts final pos/temp + run-log contents) and `tests/test_runlog.py`.
94 tests.

**Bug found + fixed during C6:** `RunLog` used a non-reentrant `threading.Lock`;
`close()` held it and called `write()` → deadlock (hung the whole suite). Switched
to `RLock`. Good argument for the integration test existing.

**Sanity checklist — run 2026-09-09, all pass:**
- ✅ every `config.yaml` key is read in the package (checked by script); `printer.connect_settle_s` added for discoverability
- ✅ every custom exception is raised somewhere (only `MagnetEmbedError`, the base, is not — by design)
- ✅ no `G28` in any sequence path (`insert_magnet` has none; `G28` only in `printer_sim` interpreter and `app.home()`, which is idle-only); no `M0`/`M25` anywhere
- ✅ `insert_magnet` restores nozzle target (or 0 on operator abort) on every failure branch — covered by tests
- ✅ `SimPrinter`↔`SerialPrinter` and `SimDispenser`↔`SerialDispenser` have identical public APIs (symmetric-diff empty) and raise the same exception types
- ✅ docs (`CLAUDE.md`, `PROJECT_PLAN.md`, this file, `HOW_IT_WORKS.md`, `TODO.md`, `README.md`) updated to match
- ✅ `requirements.txt` pinned to majors; `requirements-dev.txt` for pytest; venv steps in `CLAUDE.md` correct
- ✅ `pytest` 94/94 green; `py_compile` clean on every module; `main_sim` headless + `--gui` both run

**Files:** `tests/test_integration_sim.py`, `magnet_embed/runlog.py` (writes
`logs/run-<ts>.log`), `config` schema check in `config.py`, doc sync.

**Tests / acceptance**
- Integration: sample print → sentinel → full insert machine → resume → EOF, all
  against sims, asserting the printer ended at the right position and temp.
- `pytest` green; `python -m py_compile` clean on every module.
- Sanity checklist (run and record in `CLAUDE-LOG.md`):
  - [ ] every `config.yaml` key is read somewhere; nothing hardcoded that should be config
  - [ ] every custom exception is raised somewhere and caught or documented
  - [ ] no `G28` in any sequence path; no `M0`/`M25` anywhere
  - [ ] `insert_magnet` restores temp + position on every failure branch
  - [ ] `SimPrinter` and (future) `printer_serial` present the same interface + exceptions
  - [ ] docs (`.CLAUDE/CLAUDE.md`, `PROJECT_PLAN.md`, this file, `TODO.md`, `README.md`) match the code
  - [ ] `requirements.txt` pinned; venv instructions correct

---

## Phase 1.5 — Printer-only streaming + Pronterface-grade panel

**Why.** The printer is on the bench now; the Uno and the applicator are not. We want
to stream a real print today and use the panel for manual bring-up (jog, send raw
G-code, load filament, watch temps) — i.e. the day-to-day things Pronterface does.

**Scope guard.** No `printrun` / `printcore` dependency and **no code copied from
Pronterface** — it is GPLv3, this repo is MIT. UX inspiration only; the streaming
loop stays our own (`GcodeRunner` + `SerialPrinter`). Ports stay config-driven
(Dev Rule 3) — no serial-port scanner in the UI. Not in scope: temperature graph,
3D G-code preview.

**Chunks.** C7 printer-only entry point (done). C8 `main` runs without the Arduino.
C9–C12 land in `ui/panel.py` + `app.Controller`, so all three entry points
(`main`, `main_printer`, `main_sim --gui`) get the panel features for free.

One commit per chunk; `pytest` green + docs in the same commit, as before.

---

### C7 — Printer-only entry point  ✅  *(commit 67262e5)*

**Goal.** `python -m magnet_embed.main_printer` — a third entry point (sim vs
hardware is chosen by entry point, never a flag) that wires **only** the real
`SerialPrinter` and passes `dispenser=None` to `Controller`. Stream any sliced
`.gcode` on the real printer with no Uno attached.

`Controller.connect()` and `insert_magnet()` already handle `dispenser=None` — if a
`;MAGNET_INSERT` sentinel is hit, the panel's existing "Load a magnet" prompt is the
fallback. A plain slice (no sentinel) just streams start to finish.

**Done:** `magnet_embed/main_printer.py` + `tests/test_main_printer.py` (4 tests,
98 total). `--ping`, `--config`, `-v`, optional `gcode` positional. Docs synced
(README, CLAUDE.md entry-point / module table / Running / Deployment, TODO,
CLAUDE-LOG).

---

### C8 — `main` runs without the Arduino  ✅

**Goal.** `python -m magnet_embed.main` should launch the app **now**, before the
Uno exists — so the owner can run the real thing whenever they want and it just
gains the dispenser once it's wired. `main_printer` stays the deliberate
"printer-only" entry point; this makes `main` degrade gracefully instead of
failing at `dispenser.connect()`.

**Design.**
- `main.py` gets `--no-dispenser` (skip building `SerialDispenser` entirely →
  `Controller(printer, None, …)`).
- Without the flag: build the dispenser, but if `dispenser.connect()` raises
  (`DispenserError` / connection error) during `controller.connect()`, log a clear
  warning and **continue printer-only** for this session (`controller.dispenser`
  set to `None`). A sentinel then falls back to the operator "Load a magnet" prompt.
- `--ping` already reports printer and dispenser independently — keep, but make the
  dispenser failure non-fatal to the return code when `--no-dispenser` is given.
- `Controller.connect()` grows a `dispenser_optional: bool` (default `False`,
  preserving current strictness) — when `True`, a dispenser connect failure emits a
  `log`/`error` event, drops `self.dispenser` to `None`, and does not raise.

**Done:** `Controller(..., dispenser_optional=True)` ctor flag — a `DispenserError`
from `dispenser.connect()` is caught, a `log` event explains it, `self.dispenser`
drops to `None`, no raise. Default `False` keeps the old strictness. `main.py`:
`_build(with_dispenser=…)`, `--no-dispenser` flag, `--ping` prints
`dispenser SKIPPED` when off, GUI path passes `dispenser_optional=True` and only
`PrinterConnectionError` is fatal. `tests/test_main.py` (4) + 3 in `test_app.py`;
105 tests. Docs synced (CLAUDE.md Running + module table + `Controller` section,
README, TODO, CLAUDE-LOG).

---

### C9 — Manual G-code entry  🟢

**Goal.** A Pronterface-style command line: type `G1 X10 F600` / `M114` / `M303`,
hit Send (or Enter), see the reply in the log. Idle only (blocked mid-run).

**Files:** `magnet_embed/app.py` — `Controller.send_command(line: str)`:
strip; ignore blank; ignore + log while running; `_emit("log", f"> {line}")`;
`reply = self.printer.command(line)`; if reply `_emit("log", f"< {reply}")`;
`_emit_state()`; wrap `PrinterError` / `AckTimeout` → `_emit("error", …)` (don't
raise into the Tk callback). `magnet_embed/ui/panel.py` — an Entry + "Send" button
row, `<Return>` bound, disabled while `self.c.running`.

**Tests / acceptance**
- `send_command("M114")` calls `printer.command("M114")` once, echoes `>`/`<` to the log.
- Blank / whitespace input → no call.
- While a run is active → ignored with a log line, no `printer.command`.
- `printer.command` raising `PrinterError` → an `error` event, no exception out of the method.

---

### C10 — Live idle polling  🟢

**Goal.** While connected and idle, refresh position + temps automatically (~2 s)
so the readout tracks reality without clicking — Pronterface's always-on monitor.

**Design.** Panel-driven (no new thread): the existing 120 ms `_poll` gets a tick
counter; every `ui.idle_poll_s` seconds, if `self.c.connected and not self.c.running`,
call `Controller.refresh_state()` → `printer.command("M105")` (temps absorbed from
the `ok T:…` payload by both links) then `_emit_state()` (`M400`+`M114` → position).
New config key `ui: { idle_poll_s: 2.0 }` (0 disables). `Controller` gains a
`connected` property (a flag set in `connect()`).

**Trade-off (documented).** `refresh_state()` does blocking serial I/O on the Tk
main thread; on an unresponsive printer the UI stalls up to `ack_timeout_s`. Fine
for a bench tool and matches Pronterface's model; moving it to the reader thread
(or Marlin `M155` auto-report) is a possible follow-up.

**Tests / acceptance**
- `refresh_state()` sends `M105` then queries state; emits one `state` event.
- No-op when not connected or while running.
- `idle_poll_s: 0` → panel never calls `refresh_state()` (assert on a fake controller).
- Config: `ui.idle_poll_s` present in `config.yaml`, validated as a number ≥ 0.

---

### C11 — Extrude / retract  🟢

**Goal.** Load/unload filament from the panel: an amount (default 5 mm) + feedrate
(default 300 mm/min), Extrude and Retract buttons. Idle only.

**Files:** `magnet_embed/app.py` — `Controller.extrude(mm: float, feed: float)`:
ignore + log while running; `printer.command("M83")`; `printer.command(f"G1 E{mm:g} F{feed:g}")`;
restore prior E mode is **not** needed (jog already leaves G91→G90; extruder mode is
reset by every slice preamble) — but note it. Retract = negative `mm`. Cold-extrude
safety is left to firmware (`M302`); the resulting `Error:` surfaces via the C9 error path.
`magnet_embed/ui/panel.py` — a "Filament" LabelFrame with the two entries + buttons.

**Tests / acceptance**
- `extrude(5, 300)` → `M83` then `G1 E5 F300`.
- `extrude(-2, 300)` → `G1 E-2 F300` (retract).
- While running → ignored, no commands.

---

### C12 — Run progress  🟢

**Goal.** During a stream, show `line 1234 / 5678  (22%)` and a progress bar.

**Design.** `Controller.progress` property → `(sent, total)` from
`self.runner` (`(0, 0)` when no runner). Panel reads it in `_poll` while running and
updates a `ttk.Progressbar` + label. `runner.total_lines` counts every file line
(comments/blanks included) so the bar tops out slightly below 100 % at EOF — the
`done` event carries the true final counts; label switches to "done N/N" then.

**Tests / acceptance**
- `Controller.progress` is `(0, 0)` before a run, `(sent, total)` during, final counts after.
- Manual: bar advances while `main_sim --gui` streams `tests/data/sample.gcode`.

---

## Phase 1.6 — One entry point, bring-your-own-G-code, visual insert planning

**Why.** The owner slices in Creality Print already and brings a finished `.gcode`.
There is no value in the host doing (or shelling out to) a slicer. What is missing
is: a single `python main.py` to run everything, a way to *see* the sliced toolpath
and the magnet-insert motion before committing to hardware, a GUI to place the
sentinel and save the file, and the panel polish (raw G-code, idle polling,
extrude/retract, progress) that was scoped as C9–C12.

**Supersedes.** `project/PROTO_PLAN.md` (the never-executed `proto/` rewrite,
removed in commit 409fb10) — its one durable decision, *drop the slicer*, is folded
in here. We **extend `magnet_embed/`**; the 105-test core is not rewritten.

**Scope guard.** No slicing, no `printrun` dependency, no firmware reflash. Sentinel
stays an inert `;MAGNET_INSERT` comment so the saved file still prints from microSD
(Dev Rule 4). Arduino sketch stays deferred — every real run is `dispenser=None`
with the operator "Load a magnet" prompt until the owner says otherwise. `matplotlib`
is added to `requirements.txt` (flag `uv` per Dev Rule 9).

**Target workflow — what `main.py` does.**

```
launch main.py [--sim | --printer | --hardware]        mode chosen by flag, not by code
  │
  ├─ general controls   jog X/Y/Z · home · set temps · raw G-code · extrude/retract · live readout
  ├─ Import G-code       a finished slice from Creality Print
  ├─ Visualise           full toolpath from that file (2D layer view + 3D)
  ├─ Plan magnet insert  pocket X/Y · seat Z · shear dir · layer/height
  │                        → envelope check → watch the insert motion simulated
  ├─ Save                <stem>.magnet.gcode  (sentinel comment, microSD-valid) → auto-loads
  ├─ Run                 stream the saved file over serial to the printer
  └─ At the sentinel     park → operator dispenses → press → shear → Success / Retry / Abort → resume
```

**One commit per chunk; `pytest` green + docs in the same commit; `Co-authored-by` trailer.**

---

### C13 — Root `main.py` + mode dispatch + `send_command`  🟢

**Goal.** `python main.py` at the repo root runs the whole thing. After this chunk
the owner can drive sim / printer / hardware from one command.

- `main.py` (repo root): `--sim` (default), `--printer`, `--hardware`; plus `--ping`,
  `--no-gui`, `--config`, optional `gcode` positional. Builds the matching links
  (reuse `magnet_embed.main._build` / `main_sim` wiring — refactor the shared bits
  into `magnet_embed/entry.py` so there is no copy-paste), makes a `Controller`,
  launches the panel. `magnet_embed/main*.py` stay working as thin shims that call
  `entry`.
- `Controller.send_command(line)` (was C9): strip; ignore blank; ignore + log while
  running; `> line` / `< reply` to the log; `_emit_state()`; `PrinterError` /
  `AckTimeout` → `error` event, never raises into the Tk callback.
- Panel: a raw-command Entry + Send row, `<Return>` bound, disabled while running.

**Tests / acceptance**
- `main.py --sim --no-gui --ping` connects the sims and exits 0; `--printer` /
  `--hardware` build the right link classes (assert types with a patched serial).
- `send_command("M114")` → one `printer.command("M114")`, `>`/`<` in the log; blank
  → no call; while running → ignored with a log line; `PrinterError` → `error` event.
- `python -m magnet_embed.main_sim --gui` still works (shim).

---

### C14 — Toolpath model (`gcode/toolpath.py`)  ✅

**Done:** `parse_toolpath(path) -> Toolpath`; `Segment(p0, p1, extruding, layer,
feed)`; layer→Z table from `postprocess._detect_layers` markers, falling back to a
Z-rise heuristic for unmarked files (the PrusaSlicer fixture has `;Z:` comments but
no Z moves — markers carry it). `Toolpath` exposes `layer_count`, `move_count`,
`top_z`, `extrude_distance`/`travel_distance`, `est_time_s`, `segments_in_layer`,
`layer_for_z`. `tests/test_toolpath.py` (9). 139 tests.

**Goal.** Turn a `.gcode` file into something drawable and measurable.

- `parse_toolpath(path) -> Toolpath`: ordered segments `(x0,y0,z0)-(x1,y1,z1)`,
  `extruding: bool` (E advancing with XY), `layer: int`, `feed`. Layer table from
  `;LAYER:` / `;LAYER_CHANGE`+`;Z:` (reuse `postprocess._detect_layers`), Z-move
  fallback when unmarked. Bounding box, move count, layer count, crude time estimate
  (Σ distance ÷ feed). Absolute/relative + `G92` aware (share `gcode/util.parse_words`).
- Pure, dependency-free, streaming read (don't hold the whole path list twice).

**Tests / acceptance**
- `tests/data/sample.gcode`, `cura_sample.gcode`, `prusa_sample.gcode`: expected
  layer counts, bounding box, first/last segment, travel-vs-extrude split.
- Relative moves (`G91`) and `G92 E0` handled.
- A file with no layer markers still yields segments + a Z-derived layer table.

---

### C15 — Shared insert geometry (`sequences/geometry.py`)  ✅

**Done:** `sequences/geometry.py` — `compute_targets` (approach_xy, press_z,
shear_xy, safe_z), `plan_insert_moves` (8 phase-tagged nozzle waypoints:
PARK/APPROACH/PRESS/SHEAR/LIFT/CLEAR/RESUME×2), `check_envelope` (list of bad-target
labels), `pole_point`. `insert_magnet` refactored to build its targets and its
envelope check here — the C2 assertions (targets, no `G28`, restore-on-error) pass
untouched; the old local `_SHEAR_VEC` / `_check_envelope` removed.
`tests/test_geometry.py` (7). 146 tests.

**Goal.** One function computes the insert motion; the sequence executes it and the
viewer draws it, so they can never disagree.

- `plan_insert_moves(mi, config, saved: PrinterState) -> list[InsertMove]` where
  `InsertMove = (phase: str, gcode: str, endpoint: tuple|None, kind: str)` covering
  PARK → APPROACH → PRESS → SHEAR → LIFT → RESUME (DISPENSE/ASK are non-motion).
- `check_envelope(mi, config, saved) -> list[str]` (names of out-of-range targets)
  — `insert_magnet` keeps raising `OutOfEnvelopeError`; the dialog uses the list form.
- Refactor `insert_magnet` to emit these moves. **No behaviour change** — the C2
  assertions (targets, no `G28`, restore-on-error) stay green untouched.

**Tests / acceptance**
- `plan_insert_moves` targets == the values C2 already asserts (`pocket − offset`,
  `seat_z − offset.z`, lateral shear).
- `check_envelope` flags the same cases `_check_envelope` raises on.
- `insert_magnet` test suite unchanged and green.

---

### C16 — Insert-motion visualisation (`viz/preview.py`, matplotlib)  ✅

**Done:** `viz/toolpath_fig.py` — pure helpers (`nozzle_waypoints`,
`pole_waypoints`, `sample_polyline`, `state_at_z`, `phase_labels`) + matplotlib
`draw_layer_xy` / `draw_side_xz` / `draw_path_3d` / `draw_insert_overlay` /
`update_insert_marker`. `viz/preview.py` — `PreviewWindow` (Tk `Toplevel` +
`FigureCanvasTkAgg`): X–Y layer panel + X–Z side panel, layer slider, play/scrub
the nozzle + pole tip along `plan_insert_moves`, envelope violations flagged red,
"Open 3D view". `entry.preview()` + `python main.py --preview FILE` (overlays the
plan if the file has a sentinel). `matplotlib>=3.8,<4` added to `requirements.txt`
(**uv migration still pending** — Dev Rule 9). `tests/test_viz.py` (6, headless —
figure builders on a bare `Figure`, no display). 152 tests. HTML-export fallback
not needed — the Tk/matplotlib animation is responsive enough.

**Goal.** See the toolpath and watch the magnet-insert motion before touching hardware.

- `viz/toolpath_fig.py` — pure figure builders: `layer_axes(toolpath, layer)` (2D
  top-down), `path_axes3d(toolpath)` (3D), `overlay_insert(ax, moves, offset)`
  (nozzle path + pole-tip path, phase-coloured), `mark_envelope(ax, bad)`.
- `viz/preview.py` — `PreviewWindow(Toplevel)` with `FigureCanvasTkAgg`: layer
  slider, 2D/3D toggle, play / pause / scrub the tip along `plan_insert_moves`,
  envelope violations in red. Opened from the panel and from `main.py --preview FILE`.
- `matplotlib` → `requirements.txt`; note `uv` in the commit body.
- **Fallback (documented, not built now):** if the Tk/matplotlib animation is
  sluggish, `viz/` also gains `export_html(toolpath, moves) -> path` reusing the
  same builders' data and opens it in the browser.

**Tests / acceptance**
- Figure builders unit-tested on data only (segment counts, colour per phase,
  bad-target list) — no display needed.
- `preview.py` widget: smoke test only (construct with a dummy root), like `panel.py`.
- Manual: `python main.py --sim --preview tests/data/sample.gcode` shows the puck
  path + the insert animation.

---

### C17 — "Plan magnet insert" dialog + save (`ui/`)  ✅

**Done:** `ui/plan_dialog.py` — `PlanInsertDialog` + pure helpers `resolve_target_z`
(layer index → its Z, or Z as-is), `magnet_output_path`, `save_magnet_gcode`,
`envelope_report`. Pocket X/Y (prefilled from the toolpath bbox centre), seat Z,
shear, target (layer **or** Z); live envelope check; **Preview** → C16 window;
**Save** → `postprocess.inject_sentinel(z_mm=…)` → `<stem>.magnet.gcode` →
`controller.load_gcode`. `inject_sentinel` gained `emit_pause` (+ CLI `--pause`) to
prepend a real `M0`. Panel: "Plan magnet insert…" button, idle + file-loaded only.
`tests/test_plan_dialog.py` (6) + 1 in `test_postprocess.py`. 159 tests.

**Goal.** Place the sentinel and save the file from the GUI — no CLI.

- `ui/plan_dialog.py` — `PlanInsertDialog`: pocket X / Y, seat Z, shear dir
  (`+X -X +Y -Y`), target (layer N **or** Z mm). Live envelope check against the
  current config + loaded toolpath's top Z. "Preview" → C16 window. "Save…" →
  `postprocess.inject_sentinel` → `<stem>.magnet.gcode` → `controller.load_gcode()`
  on it, log the path.
- Optional checkbox "also emit `M0` before the sentinel" (off by default) for
  standalone-print pause behaviour.
- Panel: a "Plan magnet insert…" button, enabled once a file is loaded and idle.

**Tests / acceptance**
- Dialog compute/validate logic (headless): valid input → correct `inject_sentinel`
  call + output path; out-of-envelope → blocked with a message, no file written.
- Saved file round-trips through `parse_sentinel`; still parses as G-code.
- `M0` checkbox → the `M0` line precedes the sentinel in the output.

---

### C18 — Panel finish: idle polling, extrude/retract, progress (was C10–C12)  ✅

**Done:** `Controller.connected` + `Controller.progress` `(current_line, total_lines)`;
`refresh_state()` (`M105` then `_emit_state()`, no-op disconnected/running);
`extrude(mm, feed)` (`M83` + `G1 E…`, negative = retract, no-op running). Panel:
`ttk.Progressbar` + `line N / total (pct)` (→ `done N/N` on the `done` event), a
Filament frame (mm/feed + Extrude/Retract), and a panel-timer idle poll every
`ui.idle_poll_s` (config key, validated ≥ 0; `0` disables). `test_app.py` +6,
`test_config.py` +2. 167 tests.

- `Controller.refresh_state()` — `M105` then `_emit_state()`; panel-timer driven
  (no new thread) every `ui.idle_poll_s` when connected + idle; `0` disables.
  Config key `ui: { idle_poll_s: 2.0 }`, validated as a number ≥ 0.
- `Controller.extrude(mm, feed)` — `M83` then `G1 E<mm> F<feed>`; retract = negative
  `mm`; ignored + logged while running.
- `Controller.progress` property `(sent, total)` + `("progress", …)` events; panel
  `ttk.Progressbar` + `line N / total (pct)`; switches to `done N/N` on the `done` event.

**Tests / acceptance**
- `refresh_state()` sends `M105` + emits one `state`; no-op when disconnected/running.
- `extrude(5, 300)` → `M83`,`G1 E5 F300`; `extrude(-2, 300)` → retract; blocked while running.
- `progress` is `(0,0)` before, `(sent,total)` during, final counts after.

---

### C19 — End-to-end integration + docs + sanity pass  ✅

**Done:** `tests/test_workflow_sim.py` (2) — full path: raw slice → `parse_toolpath`
→ `plan_insert_moves` + `check_envelope` → `save_magnet_gcode` → `run_headless`
through `SimPrinter` → sentinel fires `insert_magnet` → `confirm→success` → EOF;
plus the out-of-envelope abort path (`run_headless` now returns 1 on any
`MagnetEmbedError`, not just `SequenceAborted`). `GcodeRunner` drops firmware-pause
codes `M0`/`M1`/`M25`/`M600`/`M601` (`pauses_skipped`) so an `emit_pause` file
streams cleanly (`tests/test_runner.py` +1). Docs synced (CLAUDE.md, README, TODO,
this file). Sanity scan recorded in `CLAUDE-LOG.md`: no `G28`/`M0`/`M25` emitted by
any sequence path; every module `py_compile`s; `SimPrinter`↔`SerialPrinter` and
`SimDispenser`↔`SerialDispenser` public APIs identical. **170 tests.**

- `tests/test_workflow_sim.py` — one test: load `sample.gcode` → `parse_toolpath` →
  `plan_insert_moves` → `inject_sentinel` → stream the saved file through `SimPrinter`
  → sentinel fires `insert_magnet` → `confirm→success` → EOF; assert final position,
  temp, and that the saved file carried the sentinel.
- Docs: `.CLAUDE/CLAUDE.md` (entry points, module table, Running, Architecture data
  flow), `project/PROJECT_PLAN.md`, `TODO.md`, `README.md`.
- `pytest` green; `python -m py_compile magnet_embed/*.py magnet_embed/**/*.py main.py`
  clean. Sanity checklist (Dev-Rule scan: no `G28`/`M0` in sequence paths, config
  fully read, sim↔serial API parity, exceptions raised somewhere) recorded in
  `.CLAUDE/CLAUDE-LOG.md`.

---

## Phase 1.7 — Embedded live-print view

**Why.** Watching the progress bar tick up doesn't show *where on the part* the
head currently is. The separate C16 preview window already draws the toolpath
and animates the planned insert motion, but only before a run starts — nothing
showed the live position while a print was actually streaming, closer to what a
slicer's progress view gives you.

---

### C20 — Live-print view embedded in the main panel  ✅

**Goal.** A small canvas in the main panel, always present, that shows the
current layer's toolpath with a marker at the nozzle's current position while a
run streams — no separate window, no extra printer traffic.

**Design decision (owner-confirmed).** Position comes from **G-code line
progress**, not a polled `M114`: `GcodeRunner.current_line` (already tracked,
already exposed via `Controller.progress`) is mapped onto the already-parsed
`Toolpath`, so the live view costs zero extra serial round-trips and never
contends with the streaming loop's send/`ok` lock — the same trade-off already
made for C10's idle poll, just resolved the other way here since a live view
ticking every ~1 s doesn't need `M114`-grade precision. The view lives directly
in the main panel (not a Toplevel), matching "watch it while the print runs."

**Done:**
- `gcode/toolpath.py` — `Segment` gained `line_no` (1-based, matches
  `GcodeRunner.current_line`); `Toolpath.progress_position(current_line)` and
  `Toolpath.progress_layer(current_line)` bisect the (already line-ascending)
  segment list to the last completed move — no per-call rebuild, cached in
  `__post_init__`.
- `viz/toolpath_fig.py` — `draw_live_layer(ax, tp, layer)` (the C14 layer view
  plus an empty marker artist) + `update_live_marker(artists, point)` (move the
  marker without redrawing the whole layer — what keeps per-tick updates cheap).
- `app.Controller` — caches `self.toolpath` on `load_gcode()` (best-effort: a
  parse failure logs `"no toolpath preview (...)"` and leaves `toolpath = None`
  rather than blocking the load, since the live view is optional, not required
  to run); `progress_point` property = `toolpath.progress_position(current_line)`,
  `None` with no usable toolpath.
- `ui/panel.py` — a "Live print view" `LabelFrame` embedding a small
  `FigureCanvasTkAgg`; `_sync_live_view()` redraws the layer on a layer change,
  else just moves the marker; throttled off the existing `_tick` counter via a
  new `ui.live_view_poll_s` config key (same pattern as `ui.idle_poll_s`;
  default 1.0 s, `0` disables). Static (current layer, no marker) once a file
  loads; marker starts moving once a run starts; freezes at the final position
  when the run ends.
- `config.yaml` / `config.py` — `ui.live_view_poll_s`, validated like
  `idle_poll_s` (number ≥ 0).
- Tests: `test_toolpath.py` (+3: line-progress bisect, layer lookup, empty
  toolpath), `test_viz.py` (+1: marker artist headless), `test_app.py` (+5:
  toolpath caching, `progress_point` before/during a run, a bad path doesn't
  block `load_gcode`, current-step text tracks progress), `test_config.py`
  (+2: default + validation). **209 tests.**
- Manual: a driven-widget smoke test (`ControlPanel` against a real `Tk` root,
  sim printer, `tests/data/sample.gcode`) confirmed the live view walks all 5
  layers and the marker lands on the last move's endpoint — not just unit-level
  pieces in isolation.

**Not built (documented, deferred):** a 3D live view (the C16 3D window stays
separate/static); showing the *planned remaining* path ahead of the marker
(today only what's been streamed is drawn, matching "how much is done", not
"what's left" — a possible follow-up).

**Follow-on (same session):** a "current step" label under the canvas showing
the raw text of the G-code line the runner is currently on
(`Controller.current_line_text`, from a `gcode_lines` cache also filled in
`load_gcode()`) — "what the current step looks like" as text alongside the
plot, not just a dot on it.

---

## Phase 1.8 — Consistent temp polling (verified already done) + Z-offset calibration

**Why.** Owner asked (1) whether live bed/nozzle temp polling and mid-print
temp changes were already wired up, and (2) for a Z-calibration button.

**(1) is already done, no code needed** — confirmed by re-reading the shipped
behaviour: `ControlPanel._poll()` calls `Controller.refresh_state()` on the
`ui.idle_poll_s` timer with **no** `not running` guard, and its docstring
("safe during a run too") is backed by `test_refresh_state_allowed_while_running`.
`Controller.set_temp()` is likewise allowed mid-print (locked against the
streaming loop, blocked only while the magnet-insert sequence owns the
heaters) - `test_set_temp_allowed_while_running`. Both shipped in the
2026-09-15 GUI-polish session, before this one.

---

### C21 — Z-offset calibration ("Z Calibrate…")  ✅

**Goal.** A guided paper-test workflow from the panel to (re)tune the CR-Touch
probe's Z offset, since the V3 SE's own one-touch Z sensor is only reachable
from the stock touchscreen (established in the 2026-09-15 first-layer
root-cause session — not host-accessible).

**Design decision — config as the trusted offset, not a printer readback.**
The obvious approach — read the current `M851` value off the printer, nudge,
write it back — depends on parsing the firmware's `M851` report text, which
has **not been verified** for this printer's firmware fork. Getting that parse
wrong and silently trusting a garbage value is a real bed-crash risk. Instead
`config.zcal.probe_z_offset` is the single source of truth the app trusts —
exactly the pattern already proven for `magnet_tool_offset` (Settings dialog):
measure it once for real (`M851` from a terminal), put it in config, and every
future calibration adjusts *that* value by the nudged delta rather than
reading anything back from the printer.

**Done:**
- `config.yaml` / `config.py` — new `zcal` section (`x`, `y`, `start_z`,
  `step_mm`, `feed`, `probe_z_offset`), required + numeric-validated like
  every other section.
- `app.Controller` — `start_z_calibration()` (`G28` then travel to
  `zcal.{x,y,start_z}`), `nudge_z(delta)` (slow relative Z move at
  `zcal.feed`), `save_z_offset(cumulative_delta)` (`new = zcal.probe_z_offset
  + cumulative_delta`; sends `M851 Z<new>` + `M500`; persists via
  `config.save_local_override` and updates `self.config` in place — same
  apply-immediately behaviour as the Settings dialog's offset field). All
  three idle-only, matching `home()`/`level_bed()`.
- `ui/zcal_dialog.py` — `ZCalDialog`: a safety-first guided flow (explicit
  confirm before homing/moving, explicit confirm before Save, a fine step
  selector defaulting to 0.05 mm, a live "would save X.XXX mm" preview,
  Close always lifts Z clear via the existing `jog()` — whether or not the
  offset was saved, so the nozzle never sits near the plate). Opened from a
  new "Z Calibrate…" button next to "Level Bed…" in the panel's jog frame,
  idle-only like the rest of that row.
- Tests: `test_config.py` (+2: default + validation), `test_app.py` (+7:
  homing/travel command shape, idle-only guards on all three actions,
  `M851`/`M500` command shape, config persistence via a mocked
  `save_local_override` — deliberately **not** exercised against the real
  `config.local.yaml`, same reasoning `test_settings_dialog.py` already
  applies). **218 tests.**
- Manual: a driven-widget smoke test (`ZCalDialog` + `ControlPanel` against a
  withdrawn `Tk` root, sim printer) walked start → nudge ×2 → save → close,
  confirmed the cumulative math, the `M851`/`M500` commands, the config
  update, and that closing the dialog lifts Z clear of the bed.

**Known gap (flagged, not fixed here):** this entire workflow is unverified on
the real V3 SE — see `.CLAUDE/CLAUDE.md` → Known Technical Debt. Bench-test it
deliberately (start with large steps, watch the machine, power switch within
reach) before trusting it for a real print.

---

## Phase 1.9 — GUI usability pass from real driving feedback

**Why.** Owner ran `main.py`'s GUI directly (sim mode, no printer attached) and
reported several things at once: the "connected" status felt meaningless with
no indication of *what* it was connected to; two calibration buttons with no
explanation of why both exist; the raw G-code send box and log seemed to have
disappeared; the live view felt choppy, not "real-time"; and asked for a 3D
isometric view plus a visual "where it's going to move" preview inside "Plan
magnet insert…" (the animated preview already existed as a separate popup -
C16 - just not discovered/embedded).

**Diagnosis (driven, not guessed) — an important process note:** a first
screenshot attempt (`ImageGrab.grab` on absolute screen coordinates) captured
the *owner's own* running window instead of the probe's, because both were on
the same physical desktop. Switched to introspection-only driving instead: a
withdrawn `Tk` root, the real `Controller`/`ControlPanel`/`PlanInsertDialog`
objects driven programmatically, state read back via `winfo_reqheight()`,
`.cget("text")`, artist data, etc. - reliable, and never touches the shared
screen. Confirmed via that method: `panel.body.winfo_reqheight()` was ~1122 px
against an 864 px screen - the send-G-code box and log genuinely were being
clipped off-screen, not removed.

### C22 — Mode/port label, scrollable panel, faster live-view redraw, 3D toggle, embedded insert preview  ✅

**Done:**
- `app.Controller.link_summary` - `"simulator"` / `"printer COM3"` / `"printer
  COM3 + dispenser COM4"` / `"... + dispenser (sim)"`, from whether
  `printer`/`dispenser` have a `.port` attribute (`SerialPrinter`/
  `SerialDispenser` do, `SimPrinter`/`SimDispenser` don't). Shown next to the
  connection status so "connected" is never ambiguous about *what*.
- `ui/panel.py` - the whole panel now lives in a scrollable `Canvas` +
  `Scrollbar` (`_build_scroll_container`; mouse-wheel bound only while the
  pointer is over the canvas, so it doesn't hijack scrolling inside a dialog's
  own widgets); `run_gui()` gives the window a sane starting size
  (640×800, `minsize` 480×360, resizable) instead of sizing to the full
  content height. Nothing is clipped regardless of screen height - it scrolls.
- Calibration buttons regrouped with one-line captions instead of just two
  bare buttons: "Level Bed…" / "probe + save bed mesh" and "Z Calibrate…" /
  "paper-test nozzle offset" - they're genuinely different procedures (ABL
  mesh vs. the single nozzle-to-bed offset), not a duplicate.
- `ui.live_view_poll_s` default lowered **1.0 s → 0.15 s** (config.yaml) - the
  live view was only ever throttled by this one knob (the layer-redraw-only-
  on-change optimization from C20 was already cheap; the real bottleneck was
  simply calling `_sync_live_view()` once a second), so motion is now ~6-7×
  more frequent, visibly smoother without materially more CPU (marker moves
  are a `set_data` call, not a full redraw).
- `viz/toolpath_fig.py` - `draw_live_3d(ax, tp)` / `update_live_marker_3d`,
  same pattern as the 2D pair. `ui/panel.py` - a "3D view" toggle button in
  the Live print view frame header (`_toggle_live_dim`): clears and rebuilds
  the embedded `Figure`'s Axes with/without `projection="3d"` (matplotlib
  can't change an existing Axes' projection in place), isometric-ish
  `view_init(elev=28, azim=-60)`, same live marker semantics as the 2D view.
- `ui/plan_dialog.py` - the dialog is now two columns: the existing fields on
  the left, and an embedded **"Insert motion preview"** on the right (X-Y +
  X-Z, phase-coloured nozzle path + dashed pole path + pocket marker) that
  redraws on every keystroke via the existing `_check()` - drawn even when
  out-of-envelope so the operator can see *why*. Built from the exact same
  `sequences.geometry.plan_insert_moves` output the real run uses (via
  `viz.toolpath_fig.plan_for`/`draw_insert_overlay`), so it can't drift from
  reality. The separate animated popup (play/scrub, "Open 3D view") stays
  available - renamed "Preview…" → **"Animate…"** to distinguish it from the
  now-always-visible static embed. Also fixed a pre-existing gap: picking a
  different shear direction didn't used to re-run `_check()`.
- Tests: `test_app.py` (+4: `link_summary` for simulator / real printer only /
  real printer + real dispenser / real printer + sim dispenser),
  `test_viz.py` (+1: `draw_live_3d`/`update_live_marker_3d` headless),
  `test_config.py` (updated default assertion). **223 tests.**
- Manual: re-ran the introspection-driving script end-to-end after the
  changes - status flips not-connected→connected correctly, mode/port label
  reads "simulator" and "printer COM3" correctly for a real-link stand-in,
  the 3D toggle actually swaps `live_ax.name` to `"3d"` and the marker holds
  real 3D data mid-run, and the Plan dialog's embedded preview draws real
  path data (15 plotted lines) with the correct envelope status text.

**Not done (flagged, not built):** detecting a genuine mid-session hardware
disconnect and flipping the status label back to "not connected" - today
nothing in `Controller` ever un-sets `_connected`, so a real cable pull
wouldn't be reflected there (it would still surface as an `error` event on the
next command). No printer is available to validate real failure behaviour
against right now; revisit once the applicator/bench work resumes.

---

### C23 — Side-by-side 2D/3D, equal-scale bed-aware 3D, progressive path reveal  ✅

**Why.** Owner drove the C22 GUI directly and asked for more: the 2D/3D toggle
should be side-by-side instead of either/or; the 3D view needed correct
equal-mm-per-axis scaling (matplotlib 3D defaults to stretching each axis to
fill the plot, which visually lies about proportions) and the full bed plate
for scale reference; the 3D path should reveal progressively as the nozzle
actually passes through it, not show the whole part upfront; and everything
(both plots, the send-G-code box, the log) needed to be more compact - "fold
its size... keep it side to side... isible in same screen."

**Done:**
- `viz/toolpath_fig.py` — `progressive_path_3d(tp, current_line)`: a pure
  prefix-scan over `tp.segments` returning X/Y/Z arrays of every *extruding*
  segment at or before `current_line`, with a `nan` break inserted wherever
  two consecutive extruding segments don't connect (a travel move between
  them) — lets one `Line3D` represent the whole printed-so-far path via a
  single `set_data`/`set_3d_properties` call instead of one artist per
  segment. `draw_live_3d(ax, tp, bed_xy)` now draws a static bed-plate
  outline (`machine.x_max`/`y_max`) and calls `ax.set_box_aspect((xr, yr,
  zr))` from the combined bed+part extent — true equal mm-per-axis scaling,
  so a wide flat part actually *looks* wide and flat instead of an
  auto-stretched cube. `update_live_3d(artists, tp, current_line)` rebuilds
  the path from `progressive_path_3d` and moves the marker together.
- **Bug found and fixed while building this:** `Line3D.set_3d_properties`
  reads its data back via `get_xdata()`, which by default returns the
  *original* object handed to `set_data` (not a recached numpy copy) — so
  passing plain Python lists left `_verts3d` holding plain lists, and
  matplotlib's own 3D draw path does `self._verts3d[0].shape` and raises
  `AttributeError: 'list' object has no attribute 'shape'`. Only bit when the
  line had ≥2 points (a 1-point marker update didn't trigger it, which is why
  C22's marker-only 3D code never hit this). Fixed by always handing
  `update_live_3d` real `numpy` arrays. `numpy` added to `requirements.txt`
  explicitly (was already a transitive matplotlib dependency, now imported
  directly).
- `ui/panel.py` — the live-print view is no longer a toggle; `live2d_*` and
  `live3d_*` are two canvases packed side by side, both always visible and
  always updated together in `_sync_live_view`. Both plots shrunk (figsize
  2.1×1.65 each, was one 4.6×3.0 plot) and the log box shortened (14 rows →
  8) to claw back the vertical space the side-by-side layout and the C22
  additions (mode label, calibration captions) had used — measured via the
  same introspection-driving approach as C22: panel content height dropped
  from **1185 px → 942 px**. Still taller than the 864 px screen driven
  against, so the C22 scrollable canvas remains the guaranteed fallback —
  shrinking the plots further started to trade away readability for not
  quite enough height regained to be worth it.
- Tests: `test_viz.py` (`draw_live_3d`/`update_live_3d` updated for the new
  `bed_xy` argument and array-returning marker/path, `progressive_path_3d`
  new: no-points-yet / first-point-appears / full-length-by-the-end).
  **224 tests.**
- Manual: re-ran the introspection-driving script — confirms no exception on
  render (the numpy fix), the 3D path length grows monotonically as a
  simulated run streams (`[0, 0, 0] … [12, 12, 12]` for the then 12-move sample
  file), the final marker lands on the last move's endpoint, and
  `ax.get_box_aspect()` reflects the real X:Y:Z proportions (`[1.35, 1.35,
  0.05]` for the square-bed, thin sample part — not stretched to `[1,1,1]`).

---

### C24 — Two-column full-screen layout, tight 3D scaling, Global/Local crop toggle  ✅

**Why.** Owner: the 3D part was "hardly visible" with "extreme gaps" in Z; asked
for a toggle between the whole bed (global) and just the part (local); asked
the window to always open full-screen with everything visible at once,
plots/log resized to actually use that space, and the live view moved beside
(not below) jog/home and temperature.

**Done:**
- `viz/toolpath_fig.py` — `draw_live_3d(ax, tp, bed_xy, *, show_bed=True)`:
  now sets explicit `set_xlim`/`set_ylim`/`set_zlim` with a controlled 15%
  margin (previously Z had no explicit limit at all - matplotlib's own
  autoscale margin was doing something looser, which is what actually made
  the Z ticks look like they had "extreme gaps"). `show_bed=True` ("Global")
  spans the real bed (`machine.x_max`/`y_max`) with the dashed plate outline
  drawn; `show_bed=False` ("Local") crops X/Y tightly to the part's own
  bbox (+15% padding) and skips the bed outline. Z always uses the part's own
  range in both modes (a full 250 mm `machine.z_max` range would defeat the
  purpose - there's no "context" value in showing 240 mm of empty Z above an
  8 mm part). `set_box_aspect` follows the same limits, so Local mode isn't
  just a camera zoom - the part's Z ratio in the box genuinely grows (0.049
  -> 0.134 for the sample file, confirmed via the introspection script -
  visibly less "flat").
- `ui/panel.py` — a "Global bed" / "Local part" toggle button
  (`_toggle_bed_view`) in the live-view header, next to the 3D view; only
  resets `_live_art3d` (the 2D view and loaded toolpath are untouched).
  **Two-column layout**: `_build_left` (jog/home, temperature, filament) and
  `_build_right` (live-print view, send-G-code, state line, log) replace the
  single stacked column: top bar/files/run/progress still span the full
  width, then the two columns sit side by side, with the right column's grid
  weight set to consume all extra width. `_build_scroll_container`'s canvas
  now also stretches `self.body`'s height to at least the canvas's own
  visible height (previously only width was stretched) - so a maximized
  window's extra vertical space reaches the weighted rows (live view, log)
  instead of leaving blank space below a short body; still falls back to the
  body's natural height (and scrolling) when content doesn't fit. `run_gui()`
  calls `root.state("zoomed")` to open maximized by default (Windows; falls
  back to a generous fixed geometry with a caught `TclError` on other
  platforms, since `"zoomed"` isn't a valid Tk state everywhere).
- Tests: `test_viz.py` (+1: `draw_live_3d` Global vs. Local - tighter X range,
  no bed-outline line artist in Local mode). **225 tests.**
- Manual: introspection-driving script (withdrawn root, real
  `entry.build_links`-constructed objects, a window sized to a simulated
  maximized display) - confirmed `body` actually stretches to fill the
  granted space (not just its minimal natural size), the Global/Local toggle
  changes X range (220 mm -> 104 mm for the sample part) and box aspect
  (0.049 -> 0.134) as designed, and the 3D path keeps growing correctly in
  either mode through a real run.

**Process note (again):** attempted a real subprocess (`python main.py`)
screenshot via its exact window handle (`FindWindowW`/`GetWindowRect`, not
blind coordinates this time) - `SetForegroundWindow` from a background
process is blocked by Windows' focus-stealing prevention, so the window never
actually raised and the grab captured the owner's IDE again. Deleted
immediately; screen capture is not attempted again on this shared desktop for
any reason - introspection-driving (withdrawn root, real objects, state read
back programmatically) is the verification method going forward.

---

## Phase 1.12 — Damage guard + Emergency Stop

### C25 — Nozzle-vs-part collision guard, damage-prevention errors, Emergency Stop  ✅

**Why.** The 2026-09-16 review found that `check_envelope` only tested bed
limits: with the default pole-above-nozzle offset the sample plan drove the
nozzle to X30 Y60 Z1 *inside* an 80 × 80 mm part and the Plan dialog said OK.
Owner asked for explicit errors whenever a move could damage the printer or
part (nozzle into the plate, nozzle into the part, impossible coordinates),
and the review flagged that there was no emergency stop at all.

**Done:**
- `sequences/geometry.py` — `check_envelope(mi, config, saved, toolpath=None)`
  is now the single damage guard: (1) pocket XY on the bed; (2) approach/shear
  XY + safe Z inside `machine.*` (messages say "nozzle" and that the offset
  pushed it out); (3) `press_z < 0` → "nozzle would hit the build plate";
  (4) with the toolpath, `_part_collisions`: nozzle at PRESS or at 10 sampled
  points along SHEAR inside `part_footprint` (bbox + `collision.
  footprint_margin_mm`) while `press_z < saved.z + collision.nozzle_clearance_mm`
  → "nozzle would enter the printed part during PRESS/SHEAR: …" with the
  numbers and the fix. `part_footprint` exported. Bounding-box footprint on
  purpose (conservative); per-layer occupancy later.
- `config.yaml` — new required `collision: {nozzle_clearance_mm: 1.0,
  footprint_margin_mm: 2.0}` (`config.py` required + numeric).
- `sequences/insert_magnet.py` — `toolpath=` keyword, passed to the guard.
  `app.Controller._on_sentinel` passes its cached toolpath; `entry.run_headless`
  parses one best-effort (headless is guarded too); `ui/plan_dialog.
  envelope_report` and `viz/preview.PreviewWindow` pass theirs — dialog,
  preview and run cannot disagree. Dialog status now reads "UNSAFE — cannot
  save:" with one bullet per reason; Save stays disabled.
- `app.Controller.emergency_stop()` — cancels the runner, injects `"abort"`
  into a pending operator prompt (`_prompt_pending`), writes `M112` via
  `send_line` with no idle guard / no lock / no `ok` wait, sets `estopped`,
  emits an `error` with the recovery steps (power-cycle or `M999`, then
  Connect). `refresh_state` is a no-op while `estopped` (no 2 s error spam
  against a halted board); `connect()` clears the flag. Send failure →
  `error` "use the printer's power switch", never raised out of the button.
- `links/printer_sim.py` — models `M112` (heaters off, `halted`; every
  later line raises `PrinterError` like a dead board) and `M999` (clears it).
- `ui/panel.py` — red **EMERGENCY STOP** `tk.Button` top-right, always
  enabled, no confirm.
- `tests/data/sample.gcode` — the fixture *was* the collision case (its first
  extrude started at the origin, footprint 0..80). First XY move is now a
  travel and the part spans X 40..80, so the pocket at X60 puts the nozzle at
  X30, legally outside; `test_workflow_sim` uses a −25 mm X offset for the
  cura coupon (spans 0..50) for the same reason, plus a new collision-abort
  workflow test.
- Tests: `test_geometry` +9, `test_insert_magnet` +1, `test_printer_sim` +1,
  `test_app` +6, `test_plan_dialog` +1, `test_config` +2, `test_workflow_sim`
  +1 → **245 tests.** Manual: rendered our own window handles (PrintWindow) —
  Plan dialog refuses a mid-part pocket with the full reason and Save
  disabled; E-STOP mid-run stops the worker, logs the recovery message, and
  the sim board refuses the sequence's error-handler `M104` exactly as a real
  halted board would.

**Not in C25 (still TODO):** safe-cancel routine; live view during the insert
phase; window/performance consolidation; UX pass.

---

## References

> **`project/RESEARCH.md`** is the comprehensive prior-art / similar-projects survey
> (OctoPNP, the IEEE 2021 in-situ-placement paper, host-control patterns, pick-and-place
> hardware, maker practice, and how each informs this build). The list below is the
> protocol-and-implementation subset used while writing the code.

**Marlin / G-code**
- Marlin G-code index — https://marlinfw.org/meta/gcode/
- M110 Set/Get Line Number (protocol notes on line-number sync) — https://marlinfw.org/docs/gcode/M110.html
- M25 Pause SD print / M24 resume — https://marlinfw.org/docs/gcode/M025.html
- M0/M1 Unconditional stop — https://marlinfw.org/docs/gcode/M000-M001.html
- M400 Finish Moves — https://marlinfw.org/docs/gcode/M400.html
- M155 auto temp report, M114 position, M115 info — marlinfw.org/docs/gcode/
- M876 Handle Prompt Response (host prompt support) — https://marlinfw.org/docs/gcode/M876.html
- G-code parsing & queuing (how `ok` / buffering works) — https://deepwiki.com/MarlinFirmware/Marlin/6.1-g-code-parsing-and-queuing

**Reference host implementations**
- Printrun `printcore.py` (the `clear` flag, `_sender`/`_sendnext`, resend, pause/resume) —
  https://github.com/kliment/Printrun/blob/master/printrun/printcore.py
- OctoPrint `comm.py` (firmware-quirk handling, `wait`/`busy`, resend) —
  https://github.com/OctoPrint/OctoPrint/blob/main/src/octoprint/util/comm.py
- OctoPrint serial config schema (every quirk toggle) — https://mkdocs.octoprint.org/reference/octoprint/schema/config/serial/
- OctoPrint virtual printer (model for `SimPrinter`) — https://docs.octoprint.org/en/main/development/virtual_printer.html
- PyGcodeSender (minimal line/ok sender) — https://github.com/ShyBoy233/PyGcodeSender
- gcode-cli (minimal ok/error flow control) — https://github.com/hzeller/gcode-cli

**Ender 3 V3 SE**
- awesome-resources-for-ender-3-v3-se → OctoPrint — https://github.com/pwlgrzs/awesome-resources-for-ender-3-v3-se/blob/main/remote-control/octoprint/README.md
- navaismo/Ender-3V3-SE (OctoPrint-focused firmware fork; documents stock quirks) — https://github.com/navaismo/Ender-3V3-SE
- ccarr0807/Ender-3V3-SE-update — https://github.com/ccarr0807/Ender-3V3-SE-update
- OctoEverywhere: Ender 3 V3 SE intro — https://blog.octoeverywhere.com/ender3-v3-se-introduction-all-you-need-to-know/

**Arduino serial**
- pyserial DTR/RTS toggle on open (issue #124) — https://github.com/pyserial/pyserial/issues/124
- Arduino forum: avoid reset on opening the port — https://forum.arduino.cc/t/serial-in-python-how-to-avoid-reset-on-opening/21552

**Embedding components via pause (prior art / mechanical)**
- Markforged: Embedding components in 3D printed parts — https://markforged.com/resources/blog/embedding-components-in-3d-printed-parts
- MLC-CAD: How to pause printing to embed hardware — https://www.mlc-cad.com/3d-printing-help-center/how-to-pause-printing-to-embed-hardware/
- Prusa forum: safely insert magnets into a print — https://forum.prusa3d.com/forum/how-do-i-print-this-printing-help/how-to-safely-insert-magnets-into-a-print/
- cura-plugin-pause-at-height-filament-swap — https://github.com/inanutshellus/cura-plugin-pause-at-height-filament-swap
