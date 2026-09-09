# Software Build Plan — Printer Control

Chunk-by-chunk implementation plan for the host software. Sits under
`project/PROJECT_PLAN.md` (which owns the overall Phase 0–3 roadmap); this file
breaks **Phase 1** (and the structural half of Phase 2) into buildable, testable
chunks. Each chunk: build → `pytest` green → stage → commit.

| | |
|--|--|
| Owner | kl mithunvel |
| Created | 2026-09-09 |
| Status | C1–C5 done (91 tests). C6 next. |
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

### C6 — Integration + full sanity pass

**Goal.** One end-to-end sim test, run logging, config validation, and a full review.

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

## References

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
