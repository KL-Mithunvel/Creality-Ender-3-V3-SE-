# Software Build Plan — Printer Control

Chunk-by-chunk implementation plan for the host software. Sits under
`project/PROJECT_PLAN.md` (which owns the overall Phase 0–3 roadmap); this file
breaks **Phase 1** (and the structural half of Phase 2) into buildable, testable
chunks. Each chunk: build → `pytest` green → stage → commit.

| | |
|--|--|
| Owner | kl mithunvel |
| Created | 2026-09-09 |
| Status | **C1–C8 done, 105 tests.** Phase 1 software + printer-only entry point + `main` runs without the Uno. **Phase 1.6 (C13–C19) is the active plan** — one root entry point, bring-your-own-G-code, visual insert planning; it absorbs the paused C9–C12. Magnet-flow hardware smoke test still pending the applicator build. |
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
  `seat_z + magnet_tool_offset.z`; SHEAR == lateral `shear.distance` along `shear_dir`.
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

### C16 — Insert-motion visualisation (`viz/preview.py`, matplotlib)  🟢

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

### C17 — "Plan magnet insert" dialog + save (`ui/`)  🟢

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

### C18 — Panel finish: idle polling, extrude/retract, progress (was C10–C12)  🟢

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

### C19 — End-to-end integration + docs + sanity pass  🟢

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
