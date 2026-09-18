# Claude Log

## 2026-09-09 — Project scoping: printer-control options + doc scaffolding

- Reviewed the repo — it was the untouched shared `CLAUDE.md` template library
  (`CLAUDE.md`, `CLAUDE-COMMON.md`, `PROJ_STARTER.md`), no project content.
- Analysed ways to control a Creality Ender-3 V3 SE for a magnet-embedding
  prototype (print a part, pause, embed a magnet in a printed pocket, resume):
  slicer pause-at-layer, Pronterface/Printrun, Python host script over serial,
  OctoPrint on a Pi, Klipper + Moonraker. Compared on manual-vs-automated,
  extra hardware, scriptability, risk to the printer, effort.
- Key V3 SE facts confirmed for the brief: Marlin-based, USB-C serial at 115200,
  microSD, **no networking**, standard pause primitives (`M0`/`M25`/`M600`).
- Owner decisions:
  - Control: **Python host script** (`pyserial` / `printrun.printcore`) + **Tkinter** panel.
  - Magnet placement: **actuated placer on a separate ESP32/Pico MCU** (Phase 2);
    operator-triggered in Phase 1.
  - Topology: **PC tethered to the printer over USB-C**; no Raspberry Pi.
- Rewrote `.CLAUDE/CLAUDE.md` as a real project brief: Project Overview, Running
  the System, Architecture (module table, data-flow diagram, threading model),
  Key Modules (intended interfaces), Key Conventions (the `;MAGNET_INSERT`
  sentinel, layer targeting, placer serial protocol), Data Files, Platform
  Constraints, Deployment Notes (Windows dev == runtime; hardware last),
  Known Technical Debt (none), 10 numbered Development Rules, phased TODO list,
  User Rules. Deleted the Schema Reference section (no data layer).
- Populated root `TODO.md` with the phased plan; wrote `README.md`.
- `CLAUDE-COMMON.md` left untouched (shared file).
- No code written yet — `magnet_embed/` package does not exist.

## 2026-09-09 — Project plan document + first commit

- Wrote `project/PROJECT_PLAN.md` — the authoritative multi-phase plan: objective
  and scope, locked decisions, architecture summary, Phase 0–3 with per-task files
  affected and success criteria, a consolidated checkbox to-do list, a risks table,
  and an open-questions section for Phase 0 findings.
- Added `.gitignore` (`.idea/`, `venv/`, `__pycache__/`, generated `*.gcode`,
  `logs/`, `config.local.yaml`).
- Cross-linked the plan from `.CLAUDE/CLAUDE.md` (TODO section + Data Files),
  `TODO.md`, and `README.md`; `TODO.md` now mirrors the plan checklist.
- Committed everything to `main` (was still just the template + the earlier
  uncommitted doc rewrite). `.idea/` excluded via `.gitignore`. (27ebf21)

## 2026-09-09 — Mechanism design nailed down; docs updated to match

- Worked through the physical sequence with the owner. Corrections from the earlier
  assumptions:
  - Dispenser MCU is an **Arduino Uno** (not ESP32/Pico). Renamed `placer*` →
    `dispenser*` throughout the docs.
  - The **servo only dispenses** one magnet from a magazine onto a holding pole.
  - **Press and shear are printer moves**, not servo moves — Z press to seat depth,
    then a short **lateral** shear so the pole slides off (vertical shear would pull
    the magnet back out). Shear direction carried in the sentinel.
  - **No `G28` mid-print** — save state, restore exact coordinates. Added Dev Rules
    11 (no homing), 12 (in-envelope check), 13 (Uno stays dumb).
  - Magnet **polarity is deterministic** via the holding pole — no per-magnet marking.
  - Assumption recorded: the applicator is a **clip-on** add-on and for now is assumed
    not to hinder normal printing (no tool-lift servo, no nozzle Z-clearance handling).
- Extended the sentinel to `;MAGNET_INSERT X<px> Y<py> Z<seat_z> S<dir>` and wrote the
  full `SAVE → PARK → DISPENSE → APPROACH → PRESS → SHEAR → LIFT → ASK → RESUME` state
  machine into `.CLAUDE/CLAUDE.md` (Architecture) and `project/PROJECT_PLAN.md` (Phase 2).
- Rewrote `project/PROJECT_PLAN.md`: §2 assumptions, §3 mechanism + decisions +
  Uno protocol, §4 state machine, §5 Phase 1/2 task tables, §6 tool-offset/reachable
  area, §7 risks, §8 open questions.
- Updated `.CLAUDE/CLAUDE.md` (overview, module table, data flow, insert-sequence
  subsection, Key Modules, Key Conventions, Platform Constraints, Deployment Notes,
  Dev Rules, Phase 2 TODO, overrides), `TODO.md`, and `README.md` to match.
- Still no code — `magnet_embed/` does not exist yet. (cf194a9)

## 2026-09-09 — Software build plan + research

- Researched host-controlled G-code streaming: Printrun `printcore.py` (`clear`-flag
  ack loop, resend, pause/resume), OctoPrint `comm.py` / serial schema / virtual
  printer (firmware-quirk handling, sim model), Marlin g-code docs (M400 gates real
  motion completion — `ok` only means "buffered"; M115/M114/M155/M109), minimal
  senders (PyGcodeSender, gcode-cli), Ender 3 V3 SE OctoPrint friction (M110, host
  action commands — plain-line streaming avoids it), Arduino auto-reset
  (`dtr=False` before open), and component-embedding-via-pause prior art.
- Wrote `project/BUILD_PLAN.md`: protocol notes (receive-line handling table,
  connect settle, M-code cheatsheet), chunks C1–C6 (files + tests + acceptance,
  one commit each), and a References section with all the links.
- Cross-linked BUILD_PLAN from `CLAUDE.md`, `PROJECT_PLAN.md`, `TODO.md`, `README.md`;
  `TODO.md` Phase 1 now tracks C1–C6.
- Decisions baked into the plan: plain-line streaming (no `M110`/checksums unless the
  printer requests resends); `M400` gates every insert-sequence phase; `SimPrinter`
  models the OctoPrint virtual-printer idea; hardware smoke test stays a manual step.

## 2026-09-09 — C1: skeleton, sim printer, sentinel, runner

- Created `venv/`, installed pyyaml + pyserial + pytest; `requirements.txt` (runtime)
  and `requirements-dev.txt` (pytest); `pyproject.toml` (pytest config, py>=3.12).
- `magnet_embed/`: `exceptions.py` (shared error hierarchy), `state.py`
  (`PrinterState`, `MagnetInsert`), `config.py` (deep-merge `config.yaml` +
  `config.local.yaml`, required-key check) + committed `config.yaml`.
- `gcode/util.py` (`strip_comment`, `parse_words`), `gcode/sentinel.py`
  (`parse_sentinel` -> `MagnetInsert` | `None`, raises `SentinelParseError`),
  `gcode/runner.py` (`GcodeRunner`: stream + `wait_ok` + `pause`/`resume`/`cancel`
  via `threading.Event`, sentinel callback, skips pure-comment lines).
- `links/base.py` (`PrinterLink`, `DispenserLink` ABCs), `links/printer_sim.py`
  (`SimPrinter` — minimal G-code interpreter: G0/G1/G28/G90/G91/G92/M82/M83/
  M104/M109/M140/M190, tracks XYZE + temps + modal state, `.sent` / `.moves` logs),
  `links/dispenser_sim.py` (`SimDispenser`).
- `sequences/insert_magnet.py` — signature + full state-machine docstring +
  `NotImplementedError` (body is C2).
- `main_sim.py` — headless: stream a file through `SimPrinter`, log `SENTINEL HIT`.
- Tests (33, all pass): `test_config`, `test_sentinel`, `test_printer_sim`,
  `test_runner`; fixture `tests/data/sample.gcode` (un-ignored in `.gitignore`).
- Bug fixed mid-chunk: `SimPrinter` `G28 X` (bare axis letter) was homing all axes —
  `_home_axes` now scans raw tokens, not `parse_words` output.
- `main_sim tests/data/sample.gcode`: 18/25 lines sent, 1 sentinel, final pos correct.

## 2026-09-09 — C2: insert-magnet state machine

- Implemented `sequences/insert_magnet.py` — SAVE → PARK → DISPENSE → APPROACH →
  PRESS → SHEAR → LIFT → ASK → RESUME, every phase gated with `M400`, no `G28`.
- `prompt(stage)` now takes a stage: `"dispense"` (`ready`/`abort`, only when no
  dispenser) and `"confirm"` (`success`/`retry`/`abort`). Retry re-runs from
  DISPENSE up to `sequence.max_retries`, then aborts. Abort sets nozzle to 0; any
  other error restores the saved nozzle target — both re-raise (Dev Rule 5).
- Fixed the offset convention: `magnet_tool_offset` is **(pole tip − nozzle tip)**,
  so press Z = `seat_z − offset.z`. Updated CLAUDE.md Key Conventions + diagram.
- Envelope check runs before ANY motion and covers approach XY, shear XY, press Z,
  safe Z (Dev Rule 12).
- `config.yaml`: added `travel.feed` and `sequence.max_retries`; `retract` / `prime`
  now required keys. `SimPrinter._move` no longer records a move for `G1 F…` only.
- `main_sim` runs the real sequence with `--confirm {success,retry,abort}`.
- Fixture `sample.gcode` coords made envelope-legal (`;MAGNET_INSERT X60 Y60 Z6 S+X`).
- 44 tests pass (11 new in `test_insert_magnet.py`); `py_compile` clean.
- Next: C3 — `gcode/postprocess.py` (sentinel injection + CLI).

## 2026-09-09 — Plain-language guide + patent disclosure draft

- Wrote `project/HOW_IT_WORKS.md` — plain-language walkthrough: the idea, the
  hardware, the G-code / ok-handshake / M400 / sentinel mechanics, the insert
  sequence phase-by-phase with rationale, module-by-module software map, why the
  simulator exists, glossary.
- Read `docs/Invention DisclosureForm -Khurana & Khurana.docx` (27-question K&K
  form) and wrote `docs/INVENTION_DISCLOSURE_DRAFT.md` — drafted answers for all 27
  from the project docs, with `[INVENTORS TO COMPLETE]` markers for prior-art
  search, drawings, companies, market figures, validation data, inventor details.
  Flagged: this repo has a remote — **public disclosure risk**, consult the K&K
  agent before publishing; confirm college IP policy + the teacher's role.
- `~$*` added to `.gitignore`; the `.docx` itself is committed as project material.
- Docs cross-linked from README + CLAUDE.md.
- Cleanup: C2's `git add -A` had also swept the user-dropped `.docx` **and** a Word
  `~$` lock file into commit c5c647e. Lock file removed from tracking here
  (`git rm --cached`), now gitignored. The `.docx` is kept (wanted project material).

## 2026-09-09 — C3: G-code post-processor

- `gcode/postprocess.py` + CLI — injects `;MAGNET_INSERT X Y Z S<dir>` at a chosen
  layer or Z height. `_detect_layers` understands Cura `;LAYER:<n>` (layer height
  from the first Z move) and PrusaSlicer `;LAYER_CHANGE` + `;Z:`; the sentinel is
  placed right after the marker block so it doesn't split the Prusa pair.
- `PostprocessError` (new) for: no markers, layer not found, height above the top.
- `fmt_number` moved from `insert_magnet` into `gcode/util.py` (shared).
- Fixtures `tests/data/cura_sample.gcode` + `prusa_sample.gcode`; `test_postprocess.py`
  (12 tests incl. CLI + round-trip through `parse_sentinel`). 56 tests total.
- UI defaults decided for C4 (told the user, open to veto): jog steps 0.1/1/10 mm;
  Success/Retry/Abort as a modal dialog; read-only log pane, no raw G-code entry.

## 2026-09-09 — C4: control panel + threading mediator

- `app.Controller` — headless mediator, no Tkinter. Worker thread runs
  `GcodeRunner.run()`; worker→UI via an events `Queue` drained by `poll_events()`;
  the insert sequence's `prompt(stage)` posts a `("prompt", stage)` event then
  blocks on an answers `Queue` until the UI calls `answer_prompt(value)`. Actions
  (`connect`/`load_gcode`/`jog`/`home`/`set_temp`/`start_run`/`pause`/`resume`/
  `cancel`) — the printer-touching ones are no-ops while a run thread is alive.
- `ui/panel.py` — `ControlPanel` (thin Tkinter view) + `run_gui()`: connect / load /
  run controls / jog+home (idle only) / temps / read-only `ScrolledText` log / live
  state line; modal `Success/Retry/Abort` (and `Ready/Abort`) dialog that can't be
  closed without choosing.
- `SimPrinter(command_delay=…)` added so a streamed run takes real wall-clock time
  (needed for the GUI feel and for deterministic pause/jog tests).
- `main_sim` gained `--gui` (`gcode` arg now optional with `--gui`).
- `test_app.py` — 8 mediator tests (full run w/ prompt, abort, jog-idle,
  jog-rejected-running, pause/resume, cancel, no-file, load-rejected). 64 total.
- GUI smoke-tested: `ControlPanel` constructs + `root.update()` runs clean.

## 2026-09-09 — C5: real serial links

- `links/_marlin_rx.py` — `classify(line)` → `ok`/`wait`/`busy`/`resend`/`error`/
  `action`/`info`; `parse_temps`, `parse_position` (M114). Pure, 13 tests.
- `SerialPrinter` — lazy `import serial`; `dtr=False` before open (Creality reset
  guard); `connect()` = settle + drain + `M115`→`ok` tolerating the banner;
  `wait_ok` resets its deadline on `busy:`, ignores `wait`, raises `ResendRequested`
  / `PrinterError`; G90/G91/M82/M83/feed tracked from the outgoing stream, temps +
  position absorbed from `ok`/`M114`; `query_state()` sends `M400`+`M114`.
- `SerialDispenser` — rides the ~2 s Uno reset, retries `PING`→`PONG`;
  `_cmd(send, expect_prefix)` ignores boot noise, raises `DispenserError` on `ERR`
  / timeout; `dispense`/`reset`/`status`.
- `magnet_embed/main.py` — hardware entry: `--ping` smoke test (both devices) else
  the Tkinter panel on real links. `--ping` CLIs on each link module too.
- Tests inject a `FakeSerial(responder)` transport via `transport_factory=` — no
  pyserial in the test path. 27 new tests, 91 total.
- Slow-test fix: `SerialDispenser` got a `ping_timeout_s` (default 1.0) so the
  5×-retry connect loop and the no-pong test don't burn 10 s.
- **Not done:** real hardware smoke test (needs the printer + a wired Uno).

## 2026-09-09 — C6: integration test, run logging, sanity pass  (Phase 1 software complete)

- `magnet_embed/runlog.py` — `RunLog` writes `logs/<ts>-<name>.log`, one timestamped
  line per Controller event. `Controller(log_dir=…)` opts in; `main` and
  `main_sim --gui` pass `log_dir="logs"` (git-ignored).
- `config._validate` extended: numeric keys must be real numbers (not bool),
  `gcode.sentinel_token` must be a `;` comment, `temps.standby_nozzle_c` number-or-null.
  Added `printer.connect_settle_s` to `config.yaml`.
- `tests/test_integration_sim.py` (full end-to-end run + abort, checks final
  position/temp and run-log contents) + `tests/test_runlog.py`. 94 tests.
- **Bug fixed:** `RunLog` used `threading.Lock` (non-reentrant); `close()` held it and
  called `write()` → deadlock that hung the whole test run. Now `RLock`. The
  integration test is what surfaced it.
- Ran the C6 sanity checklist (results in `project/BUILD_PLAN.md` → C6): every config
  key used; every exception raised; no `G28` in the sequence path, no `M0`/`M25`;
  Sim/Serial link APIs identical; failure branches restore temp; docs synced;
  `pytest` 94/94, `py_compile` clean, `main_sim` (headless + `--gui`) run.
- **Phase 1 software is complete.** Remaining Phase 1/2 work is hardware: build the
  applicator, write `dispenser_fw/`, measure the offset, run the manual smoke test.

## 2026-09-09 — Prior-art / similar-projects research

- Wrote `project/RESEARCH.md`. Key find: **OctoPNP** (`github.com/platsch/OctoPNP`)
  and the **IEEE 2021 paper "Automated In-Situ Placing of Metal Components Into 3D
  Printed FFF Objects"** are the closest published work — modified Prusa i3, powered
  electromagnet gripper on a rotary stepper + slip-ring, augmented slicer generating
  cavities + G-code, printed bed part-tray, 2 cameras + OpenCV, OctoPrint plugin.
- Our differentiators, sharpened: no placement actuator (servo only feeds), printer
  motion does the press + **lateral shear** release, no vision, inert `;` comment
  marker, stock firmware, host-side offset transform.
- Confirmed our design against: OctoPrint `@pause` (in-stream marker → host action,
  never sent to printer — same pattern as our sentinel); OctoPrint
  GCodeSystemCommands (gcode → servo); Klipper `PAUSE`/`RESUME` + `SET_GCODE_VARIABLE`
  (state save/restore); Marlin `M125` (we do the host-side equivalent).
- Pulled maker practice into Phase 0: pocket +0.1–0.3 mm, 2–3 cap layers, nothing may
  protrude above its cavity, oil-on-walls kills adhesion, CA-glue fallback.
- Updated `docs/INVENTION_DISCLOSURE_DRAFT.md` Q5/Q6/Q11/Q19/Q27 with the OctoPNP /
  IEEE prior art and the bed-tray staging variant. Cross-linked RESEARCH.md from
  README, CLAUDE.md, BUILD_PLAN, and the disclosure draft.

## 2026-09-09 — venv consolidation + first real-printer link test

- Two virtualenvs existed side by side (`venv/` with deps, a fresh `.venv/` from
  PyCharm with only pip). Consolidated on **`.venv`** per owner: deleted `venv/`,
  installed `requirements-dev.txt` into `.venv`, `pytest` 94/94 green there.
- Updated the venv instructions in `README.md` and `.CLAUDE/CLAUDE.md` to `.venv`
  and `requirements-dev.txt`. `CLAUDE-COMMON.md` still shows generic `venv/` paths —
  shared file, left untouched; raise with the owner if the template should change.
- Owner sliced a real part (`Cube_PETG_7m59s.gcode`, Creality Print V7, 46 layers,
  gitignored). Note: this slicer emits PrusaSlicer-style `;LAYER_CHANGE` blocks but a
  malformed height line (`;:0.2`, not `;Z:0.2`) — `postprocess --z` won't match;
  use `--layer N`. `--layer` matching is unaffected.
- **Printer serial link verified on real hardware for the first time.** Printer
  connected over USB-C (Uno not connected, applicator not built).
  `python -m magnet_embed.links.printer_serial --ping` → `M115` handshake OK,
  `M400`+`M114` OK, `COM3 connected; X-13.0 Y-15.0 Z0.0 nozzle 0.0/0.0` (unhomed,
  hence negative coords). `config.yaml` already had `printer.port: COM3`.
- Still pending: `main.py --ping` (blocks on the absent Uno), the applicator, the
  offset measurement, and a full print with an insert.

## 2026-09-09 — Phase 1.5 plan: printer-only mode + Pronterface-grade panel

- Owner wants to stream a real print now (printer on the bench, Uno/applicator not)
  and a Pronterface-style panel for bench work. Planned **C7–C11** in
  `project/BUILD_PLAN.md` (new "Phase 1.5" section), one commit per chunk.
- Scope guard recorded: **no `printrun` dependency, no copied Pronterface code** —
  Printrun is GPLv3, this repo is MIT. UX inspiration only; streaming loop stays ours.
  Ports stay config-driven (no UI port scanner). No temp graph / 3D preview.

### C7 — printer-only entry point ✅ (98 tests)

- `magnet_embed/main_printer.py` — third entry point (sim vs hardware stays chosen
  by entry point, never a flag). Builds only the real `SerialPrinter`; passes
  `dispenser=None` to `Controller` (both `Controller.connect()` and `insert_magnet`
  already handle that — a sentinel falls back to the "Load a magnet" operator prompt).
  `--ping` = printer-only smoke test; optional `gcode` positional pre-loads the panel.
- `tests/test_main_printer.py` — 4 tests (ping OK / ping fail → rc 1 / GUI wires
  `dispenser=None` + connects / connect failure → rc 1). Full suite 98 pass,
  `py_compile` clean.
- Docs synced: `README.md`, `.CLAUDE/CLAUDE.md` (entry points, module table,
  Running section, Deployment table, smoke-test block), `TODO.md`.
- Note: a later `main_printer --ping` on this machine returned
  `printer FAIL: could not open port 'COM3'` — the printer was powered off / cable
  out at that moment, not a code issue (the earlier `printer_serial --ping` on COM3
  succeeded). Re-check the USB link before a real run.

### C8 — `main` runs without the Arduino ✅ (105 tests)

- `Controller(..., dispenser_optional=True)`: a `DispenserError` from
  `dispenser.connect()` is caught → `log` event, `self.dispenser = None`, no raise.
  Default `False` unchanged.
- `main.py`: `_build(with_dispenser=…)`, `--no-dispenser` flag, `--ping` prints
  `dispenser SKIPPED` when off; GUI path uses `dispenser_optional=True` and only
  `PrinterConnectionError` is fatal. So `python -m magnet_embed.main` starts today
  with the Uno absent and gains it once wired.
- `tests/test_main.py` (4) + 3 in `test_app.py`. Docs synced.

### Direction change (owner, after C8) — re-plan from scratch

- Owner wants a from-scratch, hardware-first execution plan: P1 basic printer
  control validated on the bench (stream existing G-code, home, jog, temps), then
  P2 slicing (STL → G-code), then P3 pause / magnet insertion revisited. Plus a
  `proto_run.py` guided entry point that probes Uno + printer and walks
  STL → slice → add pause → stream.
- Owner asked whether to build from the Printrun/Pronterface repo. **Blocker
  raised:** Printrun is GPLv3, this repo is MIT — copying its code forces a
  relicense of the whole project. Recommendation: keep our own MIT streaming core
  (already 105 tests, C7/C8 just landed), read Printrun only for approach, and get
  slicing by shelling out to an existing slicer CLI (PrusaSlicer/OrcaSlicer console,
  CuraEngine, or Creality Print) rather than writing one or importing Cura.
- C9–C12 (Pronterface-grade panel polish) paused pending the new plan. `BUILD_PLAN.md`
  Phase 1.5 to be superseded by the new plan doc once the owner confirms direction.


---

## 2026-09-09 — Phase 1.6 planned; C13 done

- Owner reviewed what's built vs missing and confirmed: no slicing (he brings a
  finished slice from Creality Print), one `main.py`, visualise the toolpath and
  the magnet-insert motion before hardware, place the sentinel + save from the GUI,
  then stream. Build all of C13–C19, commit between each.
- `project/BUILD_PLAN.md` gained **Phase 1.6 (C13–C19)**. Supersedes the
  never-executed `project/PROTO_PLAN.md` (deleted in C19); its one durable call —
  drop the slicer — is folded in. We extend `magnet_embed/`, not rewrite it.
- Visualisation decision: **matplotlib embedded in the Tk panel** (closest to the
  browser render the owner approved, stays in-app). HTML-export fallback noted.

### C13 — root `main.py` + `magnet_embed/entry.py` + raw G-code entry ✅ (130 tests)

- `magnet_embed/entry.py`: `build_links(mode, config)` → `(printer, dispenser)`,
  `ping()`, `run_headless()`, `launch_panel()`. Link construction + the `--ping`
  smoke test now live here once (DRY).
- Root `main.py`: `--sim` (default) / `--printer` / `--hardware`; `--ping`,
  `--no-gui` (+ `--confirm`), `--no-dispenser`, `--config`, `-v`, optional `gcode`.
- `magnet_embed/main.py` / `main_printer.py` / `main_sim.py` refactored to thin
  wrappers over `entry` with a fixed mode. Their tests re-point the monkeypatch to
  the link source modules (lazy import). New `tests/test_entry.py`,
  `test_main_root.py`, `test_main_sim.py`.
- `Controller.send_command(line)` — raw G-code, idle only, `> line` / `< reply` to
  the log, `PrinterError`/`AckTimeout`/`ResendRequested` → `error` event. Panel got
  a "Send G-code" entry + button, disabled while running.

### C14 — `gcode/toolpath.py` ✅ (139 tests)

- `parse_toolpath(path) -> Toolpath`: ordered `Segment`s (travel vs extrude),
  modal G90/G91/M82/M83/G92/G28 aware. Layer→Z table from `_detect_layers`
  markers, Z-rise heuristic fallback when a file has none. `Toolpath` helpers:
  counts, `top_z`, extrude/travel distance, rough `est_time_s`, `segments_in_layer`,
  `layer_for_z`. `tests/test_toolpath.py` (9).

### C15 — `sequences/geometry.py` (shared insert-motion targets) ✅ (146 tests)

- `compute_targets` / `plan_insert_moves` / `check_envelope` / `pole_point`. The
  insert-motion numbers live in one pure module now; `insert_magnet` builds its
  targets and its envelope check from it, so the C16 preview and the C17 dialog
  draw exactly what the sequence will command.
- `insert_magnet` refactored (local `_SHEAR_VEC` / `_check_envelope` removed); the
  C2 behaviour is unchanged and its tests pass untouched. `tests/test_geometry.py` (7).
- Also removed the accidentally-committed `project/PROTO_PLAN.md` (commit 409fb10)
  and corrected the BUILD_PLAN references.

### C16 — `viz/` toolpath + insert-motion preview (matplotlib) ✅ (152 tests)

- `viz/toolpath_fig.py`: pure helpers + matplotlib `draw_*` (layer X-Y, side X-Z,
  3D path, phase-coloured insert overlay, animated tip markers). No GUI backend, so
  the builders are unit-tested on a bare `Figure`.
- `viz/preview.py`: `PreviewWindow` (Tk Toplevel + FigureCanvasTkAgg) — layer
  slider, play/scrub the nozzle + pole tip along `plan_insert_moves`, envelope
  violations flagged, "Open 3D view".
- `entry.preview()` + `python main.py --preview FILE`.
- `matplotlib>=3.8,<4` in requirements.txt. **uv migration still pending.**
- `tests/test_viz.py` (6). Looked at a headless-rendered preview once — path,
  phase colours, tip markers and the X-Z press depth read correctly.

### C17 — "Plan magnet insert" dialog + save ✅ (159 tests)

- `ui/plan_dialog.py`: `PlanInsertDialog` + pure helpers (`resolve_target_z`,
  `magnet_output_path`, `save_magnet_gcode`, `envelope_report`). Enter pocket X/Y
  (prefilled from the bbox centre), seat Z, shear, target layer/Z; live envelope
  check; Preview -> C16; Save -> `<stem>.magnet.gcode`, auto-loaded.
- `postprocess.inject_sentinel` gained `emit_pause` (+ CLI `--pause`) -> a real M0
  before the sentinel for microSD prints.
- Panel: "Plan magnet insert…" button (idle + file loaded).
- `tests/test_plan_dialog.py` (6) + 1 postprocess test.

### C18 — panel finish: idle poll, extrude/retract, progress ✅ (167 tests)

- `Controller`: `connected` flag, `progress` (current_line/total_lines),
  `refresh_state()` (M105 + state emit), `extrude(mm, feed)` (negative = retract).
  All idle-only.
- Panel: run-progress bar + `line N / total (pct)` -> `done N/N`; Filament frame
  (mm/feed + Extrude/Retract); panel-timer idle poll every `ui.idle_poll_s`.
- New config key `ui.idle_poll_s` (default 2.0, validated >= 0, 0 disables).
- `test_app.py` +6, `test_config.py` +2. (Old C9-C12 fully absorbed now.)

### C19 — end-to-end workflow test + sanity pass ✅ (170 tests) — Phase 1.6 complete

- `tests/test_workflow_sim.py` (2): raw slice -> parse_toolpath -> plan_insert_moves
  + check_envelope -> save_magnet_gcode -> run_headless through SimPrinter ->
  sentinel fires insert_magnet -> confirm=success -> EOF; plus the out-of-envelope
  abort path.
- `entry.run_headless` now returns 1 on any `MagnetEmbedError` (not just
  `SequenceAborted`) so a bad plan reports cleanly headless.
- `GcodeRunner` drops firmware-pause codes `M0`/`M1`/`M25`/`M600`/`M601`
  (`pauses_skipped`) — an `emit_pause` file streams cleanly through the host and
  still pauses on microSD. `tests/test_runner.py` +1.
- Sanity scan: no `G28`/`M0`/`M25` emitted by any sequence path (only a docstring
  mentions G28); every module `py_compile`s; `SimPrinter`<->`SerialPrinter` and
  `SimDispenser`<->`SerialDispenser` public APIs are identical (empty symmetric diff).
- Docs synced: CLAUDE.md (status, Key Conventions pause-skip bullet, runner section,
  Known Technical Debt), README (How it works + Status), BUILD_PLAN (C13-C19 all
  done + status line), TODO (Phase 1.6 -> Done).

**Phase 1.6 done.** Remaining for the magnet flow is hardware: build the applicator,
wire the Uno + write `dispenser_fw/`, measure `magnet_tool_offset`, run the manual
smoke test.

### Fix — entry files must run as bare scripts (IDE "Run file")

- `python magnet_embed/main.py` (as opposed to `python -m magnet_embed.main`)
  raised `ImportError: attempted relative import with no known parent package`.
  Added a `__package__ in (None, "")` sys.path bootstrap + switched the three
  `magnet_embed/main*.py` to absolute imports. `tests/test_entrypoints_as_scripts.py`
  runs all four entry files with `--help` via subprocess. 174 tests.

## 2026-09-15 — First bench session on the real printer; mid-print temp control

- Owner had the printer on the bench for the first time this session. Verified:
  `pytest` 174/174 green, `.venv` intact, `COM3` enumerated, `python main.py
  --printer --ping` OK (`X134.25 Y125.0 Z10.0`, nozzle cold). Streamed
  `Cube_PETG_7m59s.gcode` over `--printer` — real hardware, no sentinel involved.
- **Extrude button investigated** — looked broken ("does nothing"). Root cause
  wasn't a code bug: nozzle was at 0°C and Marlin's cold-extrusion guard blocks
  the motor while still replying `ok`, so nothing moved and nothing errored.
  Confirmed by the owner after reheating. Real gap found along the way and
  fixed anyway: `Controller.jog`/`home`/`extrude` didn't catch
  `PrinterError`/`AckTimeout`/`ResendRequested` the way `send_command` already
  did — an exception there would have escaped a Tkinter button callback
  silently (printed to stderr, nothing shown in the panel). Now all four wrap
  it and emit an `error` event.
- **Owner asked for**: current temp visible in the GUI, min/max info next to
  the entries, proper error handling, and whether changing temp mid-print
  makes sense. Answers built in:
  - `config.yaml` `temps.{nozzle,bed}_{min,max}_c` (0–260°C nozzle, 0–100°C bed;
    override in `config.local.yaml` for a hotend rated higher) — required +
    numeric in `config.py`, plus a `min < max` sanity check.
  - `Controller.set_temp` now range-checks against those before sending, and is
    the one action allowed to run **during a print** (M104/M140 don't touch
    motion, unlike jog/home/extrude) — reused across a real print, not just at
    idle, matching how every other print host (Cura/OctoPrint/Pronterface)
    behaves. Made safe with a `threading.Lock` shared between `Controller` and
    a `GcodeRunner(lock=...)` param, so the out-of-band `M104`/`M140` send/`ok`
    can't interleave with the streaming loop's own send/`ok` on the same
    serial connection. Blocked separately (`_in_insert` flag) while
    `sequences.insert_magnet` is mid-sequence, since that code drives the
    printer directly and unlocked, and Dev Rule 6 says the sequence owns the
    heaters during the pause.
  - `ui/panel.py`: Temperature frame no longer reads "(idle only)"; each
    nozzle/bed row shows `allowed <min>-<max>°C` and a live `now: A/B°C` label
    driven off every `state` event (updates right after a mid-print `set_temp`,
    not only the idle-poll ticks).
- 11 new tests (`test_config.py` +2, `test_app.py` +9) covering: range rejection
  both directions, mid-print `set_temp` succeeding, `set_temp` blocked during
  an active insert, and `PrinterError` surfacing for `jog`/`home`/`extrude`/
  `set_temp`. 185 tests total, `py_compile` clean, panel smoke-tested headless
  (`root.withdraw()`) — labels update on `connect()` and on `set_temp()`.
- Docs synced: `.CLAUDE/CLAUDE.md` (Threading model, `app.py`/`ui/panel.py`
  Key Modules, `config.yaml` module-table row, Known Technical Debt — flagged
  that there's still no periodic `M105` poll *during* a run, so the `now:`
  label only refreshes on an explicit action, and that the new max-temp guard
  rails are host-side UI limits, not read from the printer's real firmware
  ceiling).
- Not done yet: live temp polling *during* an ordinary print (would need a
  periodic locked `M105` on a Tk timer); still no applicator/Uno on the bench.

## 2026-09-15 (cont.) — First-layer root cause; 4 GUI/software polish commits

- Owner reported a poor first layer on the `Cube_PETG_7m59s.gcode` test print
  and asked to check the homing sequence against Creality's own code/docs, and
  suspected the Z-offset. Pulled the file's embedded start G-code and
  Creality's official firmware source (`github.com/CrealityOfficial/Ender-3V3-SE`):
  - Homing is fine — `Z_SAFE_HOMING` is enabled with a bed-center XY point, so
    a bare `G28` (what both the slicer and `Controller.home()` send) homes X,
    Y, then Z via the CR-Touch at bed center. Not a bug.
  - Real cause: `RESTORE_LEVELING_AFTER_G28` is **disabled** in the stock
    firmware (`Configuration.h` line 1521) while `AUTO_BED_LEVELING_BILINEAR`
    is on, so `G28` turns mesh compensation back off; the slicer's start
    G-code (`machine_start_gcode`) never sends `M420 S1` to re-enable it. That
    print ran the whole time with an uncorrected mesh against whatever tilt
    the bed actually has. Nothing in `magnet_embed` causes or fixes this -
    `GcodeRunner` streams `G28`/`G29`/`M420` through unmodified.
  - Also confirmed (same source): Z-offset itself is set via Creality's
    proprietary one-touch sensor pad (`USE_AUTOZ_TOOL_2`, enabled), calibrated
    from the touchscreen, not from the host.
  - Recommended fix (outside this repo): add `M420 S1` right after `G28` in
    Creality Print's start G-code.
- Asked "start building all the required software... gui and so on" - too
  open-ended to act on; asked a clarifying question, owner picked "GUI/software
  polish only" then "all three, one at a time, commit the intermediates."
  Delivered as four separate commits:
  1. **`53b02a8`** - `refresh_state()` no longer idle-only (it's read-only:
     `M105`/`M400`/`M114`), so the panel's `now:` temp labels stay live through
     an ordinary print, not just after an explicit action. Blocked only during
     an active insert (`_in_insert`). 186 tests.
  2. **`b29f328`** - owner's mid-turn ask, tying directly to the root-cause
     finding above: a **"Level Bed…"** panel button
     (`Controller.level_bed` = `G28`→`G29`→`M420 S1`→`M500`, idle-only,
     confirm dialog first since it can take a couple of minutes). Documented
     the caveat clearly: this does **not** survive the print's own `G28`
     unless the slicer's start G-code (or a future `GcodeRunner` change)
     re-sends `M420 S1` after it - the button fixes/refreshes the saved mesh,
     it doesn't by itself fix a print run today. 189 tests.
  3. **`e2b4c14`** - `RunLog.close()` now appends a human-readable
     `=== SUMMARY ===` block (duration, lines sent/total, sentinels seen, any
     errors, final position + temps); echoed to the panel log right after a
     run finishes. 194 tests.
  4. **`73b11fc`** - new **Settings…** dialog (`ui/settings_dialog.py`) edits
     `printer.port`/`dispenser.port`/`magnet_tool_offset` and writes
     `config.local.yaml` via the new `config.save_local_override` (deep-merge,
     never touches the committed `config.yaml`); offset changes apply on the
     next insert immediately, port changes need a restart. 198 tests. Checked
     off the matching Phase-3 items in `TODO.md` / `PROJECT_PLAN.md`.
- All four committed individually (owner's request), local `main` 5 commits
  ahead of `origin/main` — not pushed.

## 2026-09-15 (cont.) — Fixed stale TODO checkboxes; embedded live-print view (C20)

- Owner asked what software/GUI work remained. Answer: Phase 1/1.5/1.6 chunks
  (C1–C19) were all actually done; `TODO.md` still showed C8–C12 unchecked
  with a dangling "see In Progress above" pointer even though `BUILD_PLAN.md`
  showed C8 shipped and C9–C12's content folded into C13/C18. Fixed `TODO.md`
  to match (two accurate checked lines, dead cross-reference dropped).
- Owner then asked for a live view of print progress "like in the slicer" and
  to flesh out the GUI with plots. Before writing code, asked two design
  questions (`AskUserQuestion`): (1) how to get the nozzle's live position
  during a stream — derive it from G-code line progress against the parsed
  toolpath (no extra printer traffic) vs. poll real `M114` (accurate but
  contends with the runner's own send/`ok` lock, the same trade-off C10's
  idle-poll design deliberately avoided); owner picked line-progress. (2)
  where the view lives — embedded in the main panel vs. a separate window;
  owner picked embedded.
- Implemented as **Phase 1.7 — C20** (`project/BUILD_PLAN.md`):
  `gcode/toolpath.py` (`Segment.line_no`, `Toolpath.progress_position` /
  `progress_layer`, bisect-cached in `__post_init__`), `viz/toolpath_fig.py`
  (`draw_live_layer` / `update_live_marker`), `app.Controller` (`load_gcode()`
  caches a `toolpath`, best-effort — a parse failure logs and leaves it `None`
  rather than blocking the load; new `progress_point` property), `ui/panel.py`
  (embedded `FigureCanvasTkAgg` "Live print view" frame, `_sync_live_view`,
  throttled via a new `ui.live_view_poll_s` config key mirroring
  `ui.idle_poll_s`). 209 tests (+11). `py_compile` clean.
- Verified beyond the unit tests: wrote a driven-widget smoke test — a real
  `ControlPanel` against a withdrawn `Tk` root and a sim printer, streaming
  `tests/data/sample.gcode` end to end — confirming the live view actually
  walks all 5 layers and the marker lands on the final move's endpoint, not
  just that the pure helper functions work in isolation.
- Docs synced: `TODO.md`, `project/BUILD_PLAN.md` (new Phase 1.7 / C20
  section), `README.md` (status, test count, docs table), `.CLAUDE/CLAUDE.md`
  (Running-the-system status line, module table rows for `toolpath.py` /
  `toolpath_fig.py` / `app.py`, `ui/panel.py` Key Modules section).

## 2026-09-15 (cont.) — Audited temp polling; added a current-step readout + Z-offset calibration (C21); committed in phases

- Owner asked three things in one message: (1) confirm live bed/temp polling
  and mid-print temp changes are actually wired up, (2) add a Z-calibration
  button, (3) add a plot showing the G-code "along with what the current step
  looks like" — and to commit after each phase.
- (1) audited, no code needed: already true (see the C20 entry above; also
  independently confirmed by re-reading `panel.py`'s poll loop and
  `test_refresh_state_allowed_while_running` / `test_set_temp_allowed_while_running`).
- (3) was mostly already the C20 live view from earlier this session; added a
  small follow-on - a "current step" label under the canvas showing the raw
  text of the G-code line the runner is on (`Controller.current_line_text`,
  backed by a new `gcode_lines` cache in `load_gcode()`).
- (2) new: **Z Calibrate…** guided paper-test dialog (`ui/zcal_dialog.py`) +
  `Controller.start_z_calibration`/`nudge_z`/`save_z_offset` + a new `zcal`
  config section. Key design call: rather than reading the printer's current
  `M851` value back and risk trusting an unverified report-text parse (a real
  bed-crash risk if wrong), `config.zcal.probe_z_offset` is the app's trusted
  baseline - same pattern already proven for `magnet_tool_offset` - and Save
  adjusts *that* by the nudged delta, then pushes the result with `M851`+`M500`.
  Flagged prominently (dialog copy, docstrings, `.CLAUDE/CLAUDE.md` Known
  Technical Debt, a new Pre-hardware-checklist line) that this entire workflow
  is unverified on the real V3 SE.
- Caught and fixed a real test-hygiene bug while building this: an early draft
  test called `Controller.save_z_offset` without mocking `save_local_override`,
  which would have written a **real** `magnet_embed/config.local.yaml` into the
  repo on every test run (same unguarded-write pattern the Settings dialog
  already has, which is why `test_settings_dialog.py` only tests its pure
  `build_updates` helper and never calls `_save()`). Rewrote the test to mock
  `app_mod.save_local_override` instead. Also caught the same problem in my
  own manual smoke-test script (it called the real method and *did* write a
  stray `config.local.yaml` with a fake `-0.1` offset) - deleted it before
  finishing.
- Tests: 209 -> 218. Manual: a driven-widget smoke test (`ZCalDialog` +
  `ControlPanel` against a withdrawn `Tk` root, sim printer) walked
  start -> nudge x2 -> save -> close end to end, including confirming Close
  lifts Z clear of the bed afterward.
- Docs synced: `TODO.md`, `project/BUILD_PLAN.md` (new Phase 1.8 / C21
  section + a note confirming (1) needed no code), `README.md`,
  `.CLAUDE/CLAUDE.md` (status line, module table rows for `config.yaml` /
  `app.py` / `ui/panel.py` / new `ui/zcal_dialog.py`, Controller
  actions/properties, Key Conventions, Known Technical Debt, Pre-hardware
  checklist).
- Committed in phases per the owner's request: (1) the stale-TODO fix, (2) the
  C20 live view + current-step readout, (3) the C21 Z-calibration feature -
  see the commit log for exact hashes.

## 2026-09-16 — GUI usability pass (C22), driven from the owner actually running it

- Owner ran `main.py` themselves (sim mode, no printer on hand) and reported
  several things at once: "connected" status felt meaningless with no target
  shown; asked to add which COM port is which; questioned two calibration
  buttons' sizing and why both exist; asked to see the new live-view graph;
  wanted the exact current G-code line visible during a run; and asked where
  the raw-G-code send box/log had gone. Mid-turn, two more asks landed: a full
  3D isometric toggle for the live view (plus "why isn't it smooth/real-time"
  - no printer attached, so purely a sim-speed/redraw-rate question), and a
  visual "where it's going to move" simulation embedded in "Plan magnet
  insert…" (that already existed as the separate C16 animated popup - just
  not discovered/embedded).
- Tried to screenshot the running GUI to check it directly. First attempt
  (`PIL.ImageGrab` on absolute screen coordinates) captured the **owner's
  own** window instead of the probe's - same physical desktop, both windows
  near the same spot - and revealed their real in-progress work
  (`Cube_PETG_7m59s.gcode`, a live "Plan magnet insert" dialog). Stopped that
  approach immediately and told the owner; switched to introspection-only
  driving for the rest of the session (withdrawn `Tk` root, drive the real
  `Controller`/`ControlPanel`/`PlanInsertDialog` objects programmatically,
  read state back via `winfo_reqheight()`, `.cget("text")`, artist data - never
  touches the shared screen). That's how the actual clipping bug was
  confirmed: `panel.body.winfo_reqheight()` ≈ 1122 px against an 864 px
  screen - the send-G-code box and log were genuinely being clipped, not
  removed.
- Root-caused the "always says connected" report: the status text itself was
  already correct (verified `not connected` → `connected` only after a real
  `Controller.connect()`), but nothing showed *what* it was connected to, and
  `--sim` (the default with no flag) always succeeds - so with no printer
  attached the label looked suspicious even though it was accurate. Fixed by
  adding `Controller.link_summary` (`"simulator"` / `"printer COM3"` / …)
  next to the status, which also directly answers the COM-port ask.
- Shipped as **Phase 1.9 — C22**: `link_summary`; the whole panel wrapped in
  a scrollable `Canvas`+`Scrollbar` (mouse-wheel scoped to `<Enter>`/`<Leave>`
  so it can't hijack a dialog's own scrolling); calibration buttons captioned
  ("probe + save bed mesh" vs. "paper-test nozzle offset") instead of two
  bare buttons; `ui.live_view_poll_s` default **1.0 s → 0.15 s** (the
  layer-redraw-only-on-change logic from C20 was already cheap - the real
  smoothness bottleneck was simply calling the sync function once a second);
  a "3D view" toggle on the live-print view (`draw_live_3d`/
  `update_live_marker_3d`, isometric `view_init`); and an embedded live
  insert-motion preview in `PlanInsertDialog` (phase-coloured path, redraws
  on every keystroke, built from the exact geometry the real run uses) -
  kept the old popup too, renamed "Preview" → "Animate…" since it's now the
  play/scrub-specific option, not the only way to see the motion.
- Flagged, not fixed: a genuine mid-session hardware disconnect still isn't
  reflected in the status label (`Controller._connected` is never un-set) -
  no printer on hand to validate the right failure signal against, and
  guessing wrong (e.g. treating every `AckTimeout` as a disconnect) seemed
  riskier than leaving it flagged in Known Technical Debt for later.
- Tests: 218 -> 223 (`link_summary` x4, `draw_live_3d`/`update_live_marker_3d`
  x1, `test_config` default updated). Verified end-to-end via the
  introspection-driving script: status flips correctly, `link_summary` reads
  right for both a sim and a real-link stand-in, the 3D toggle actually swaps
  `live_ax.name` to `"3d"` with a live 3D marker mid-run, and the Plan
  dialog's embedded preview draws real path data with correct envelope text.
- Docs synced: `TODO.md`, `project/BUILD_PLAN.md` (new Phase 1.9 / C22
  section, including the screenshot-mishap process note), `README.md`,
  `.CLAUDE/CLAUDE.md` (status line, module table rows, `app.py`/`ui/panel.py`/
  `ui/plan_dialog.py` Key Modules sections, Known Technical Debt).

## 2026-09-16 (cont.) — 2D/3D side by side, bed-aware equal-scale 3D, progressive path reveal (C23)

- Owner asked for four more things after driving C22 themselves: (1) show the
  2D and 3D live views at the same time instead of toggling; (2) fix the 3D
  view's axis scaling to be proportionally correct; (3) draw the full bed
  plate in 3D for scale reference; (4) the 3D path (the "yellow lines")
  should only appear as the nozzle actually passes through that point, not
  show the whole part immediately; and to compact the live-view plots plus
  the send-G-code/log section so more fits on one screen.
- Implemented all four as **Phase 1.10 — C23**: `viz/toolpath_fig
  .progressive_path_3d(tp, current_line)` - a pure prefix-scan building a
  single growing `Line3D`'s worth of X/Y/Z data (with `nan` breaks between
  non-contiguous extrude runs) instead of one Line3D artist per segment;
  `draw_live_3d` now also draws a static bed-plate outline from
  `machine.x_max`/`y_max` and calls `ax.set_box_aspect((xr, yr, zr))` from
  the combined bed+part extent for true equal-mm-per-axis scaling;
  `ui/panel.py`'s live view is no longer a 2D/3D toggle - `live2d_*` and
  `live3d_*` are two canvases packed side by side, both updated every sync.
- Caught a real bug while wiring the progressive path: `Line3D
  .set_3d_properties` reads its data back via `get_xdata()`, which returns
  the *original* object passed to `set_data` (not a recached copy) - so
  passing plain Python lists (my `progressive_path_3d` return type) left
  `_verts3d` holding plain lists, and matplotlib's own 3D draw path does
  `self._verts3d[0].shape` and raises `AttributeError: 'list' object has no
  attribute 'shape'`. A 1-point marker update never hit this (that's why
  C22's marker-only 3D code worked), only a real multi-point line did.
  Fixed by converting to `numpy` arrays right before handing them to the
  artist in `update_live_3d`; added `numpy` to `requirements.txt` explicitly
  (it was already a transitive matplotlib dependency, now imported
  directly). Caught via the introspection-driving script, not by eyeballing
  the GUI - the exception surfaced as a Tkinter callback traceback the first
  time the panel actually tried to redraw after a run started.
- Compacted the panel per the "fold it... same screen" ask: both live-view
  plots shrunk from one 4.6×3.0 figure to two 2.1×1.65 figures side by side,
  log box shortened 14 rows -> 8. Measured content height via the same
  introspection script: 1185 px -> 942 px. Still taller than the 864 px
  screen driven against, so the C22 scrollable canvas stays the fallback -
  didn't shrink the plots further since that started trading away
  readability for not much more height regained.
- Tests: 223 -> 224 (`draw_live_3d`/`update_live_3d` updated for the new
  signature and array-based artists, `progressive_path_3d` new: 3 cases).
  Re-ran the introspection-driving script end to end after the fix: no
  exception, 3D path length grows monotonically across a simulated run
  (`[0, 0, 0] ... [12, 12, 12]` for the 12-move sample file), final marker on
  the last move's endpoint, `ax.get_box_aspect()` reflects real proportions
  (`[1.35, 1.35, 0.05]` - square bed, thin sample part - not stretched to
  `[1, 1, 1]`).
- Docs synced: `TODO.md`, `project/BUILD_PLAN.md` (new Phase 1.10 / C23
  section), `README.md`, `.CLAUDE/CLAUDE.md` (status line, module table rows,
  `ui/panel.py` Key Modules section rewritten for the side-by-side design),
  `requirements.txt` (`numpy`).

## 2026-09-16 (cont.) — Asked to run+check the real GUI; two-column full-screen layout, Global/Local 3D crop (C24)

- Owner asked me to run `main.py` and check the GUI myself. Tried a
  subprocess (`python main.py` for real, not an in-process probe) and
  screenshotted it by exact window handle this time (`FindWindowW`/
  `GetWindowRect`, not blind coordinates - the fix for last time's
  collision). Still captured the owner's own IDE window: `SetForegroundWindow`
  from a background process is blocked by Windows' focus-stealing
  prevention, so the launched window never actually raised, and the grab
  captured whatever was really on top. Deleted the file immediately.
  Concluded screen capture is not viable on this shared desktop *at all*,
  regardless of technique - stopped trying it, full stop. Verified instead
  via (1) the real headless entry point (`python main.py --sim --no-gui
  tests/data/sample.gcode --confirm success`, exit code 0 - real proof the
  shipped entry point works end to end, zero screen risk) and (2) the exact
  GUI code path (`entry.build_links` + `Controller` + `ControlPanel`,
  withdrawn root, state read back programmatically) - confirmed
  `link_summary`/`target_lbl` correct, layout measurements, box aspect, and
  the 3D path growing through a real run, all via the real `entry`-
  constructed objects, not hand-rolled stand-ins.
- Owner then gave four more pieces of feedback on the 3D view + layout: (1)
  the 3D part was "hardly visible" with "extreme gaps" in Z; (2) wanted a
  toggle between showing the whole bed ("global") and just the part
  ("local"); (3) wanted the window to always open full-screen with
  everything visible at once; (4) wanted the live view moved beside (not
  below) jog/home and temperature, and the plots/log to actually resize to
  use the screen.
- Root-caused the Z-gap complaint: `draw_live_3d` was calling
  `set_box_aspect` but never explicitly setting axis limits, so matplotlib's
  own autoscale margin (on top of an already-tiny Z data range next to a
  220 mm bed) is what produced the "hardly visible... weird gaps" look - not
  a bug exactly, just no intentional control over the margin.
- Shipped as **Phase 1.11 — C24**: `draw_live_3d(ax, tp, bed_xy, *,
  show_bed=True)` now sets explicit `set_xlim`/`set_ylim`/`set_zlim` with a
  controlled 15% margin; `show_bed=False` ("Local") crops X/Y tight to the
  part's own bbox instead of the bed, while Z always uses the part's own
  range in both modes (a 250 mm `machine.z_max` range would defeat the
  purpose of showing an 8 mm part at all). `ui/panel.py` gained a "Global
  bed" / "Local part" toggle button (`_toggle_bed_view`) next to the 3D
  view, and a full **two-column** rewrite: `_build_left` (jog/home,
  temperature, filament) and `_build_right` (live view, send-G-code, log)
  replace the single stacked column, with the right column's grid weight
  set to consume all extra width. `run_gui()` now calls `root.state
  ("zoomed")` to open maximized by default (Windows; falls back to a fixed
  geometry with a caught `TclError` elsewhere). Also fixed the scroll
  container so it stretches `self.body`'s *height* to the canvas's visible
  height too (previously only width was stretched) - otherwise a maximized
  window's extra vertical space would just sit blank below a short body
  instead of reaching the weighted rows (live view, log).
- Verified via the introspection-driving script (window sized to a
  simulated maximized display, real `entry.build_links`-constructed
  objects): `body` actually stretches to fill the granted space (1069×741,
  matching what was available - not just its minimal natural size); the
  toggle changes the 3D X range (220 mm "Global" -> 104 mm "Local" for the
  sample part) and the box-aspect Z ratio (0.049 -> 0.134, ~2.7× more
  visually prominent); the 3D path keeps growing correctly in either mode
  through a real run (0 -> 16 points).
- Tests: 224 -> 225 (`draw_live_3d` Global-vs-Local: tighter X range, no
  bed-outline artist in Local mode).
- Docs synced: `TODO.md`, `project/BUILD_PLAN.md` (new Phase 1.11 / C24
  section, including the second screenshot-mishap note), `README.md`,
  `.CLAUDE/CLAUDE.md` (status line, module table rows, `ui/panel.py` Key
  Modules section rewritten for the two-column layout).

## 2026-09-16 (cont.) — Approach + GUI review; patent draft refreshed; collision gap found

- Owner asked for a full-context review: what to improve in approach and
  capability, a pass over the patent draft, and a look at the running GUI
  with UI/UX and accessibility in mind. Review only, then docs — no code.
- **GUI actually rendered this time without touching the shared screen:**
  drove the real `ControlPanel` + `Controller` + sim links in-process and
  rendered *our own* window handles via Win32 `PrintWindow`
  (`GetAncestor(winfo_id, GA_ROOT)` → `PrintWindow(hwnd, dc,
  PW_RENDERFULLCONTENT)` → `GetDIBits` → PNG in the scratchpad). Unlike the
  two earlier screen-grab attempts, this can only ever contain the window we
  created. Captured the main panel (fresh, loaded, running at the sentinel,
  done; Global and Local 3D), the Plan dialog, Settings, Z-offset dialog, the
  Animate preview and the Success/Retry/Abort prompt. Screenshots deleted
  with the scratchpad; nothing added to the repo.
- **Biggest finding — a real collision gap (Dev Rule 7/12).**
  `check_envelope` tests bed limits only. With the default offset (pole 5 mm
  *above* the nozzle, 30 mm in +X) PRESS sends the nozzle to
  `seat_z − 5` at `pocket − 30` in X — inside the part unless the pocket is
  near an edge. Reproduced numerically on `tests/data/sample.gcode`: nozzle
  target X30 Y60 Z1.0 inside an 80 × 80 mm coupon printed to Z 6, envelope
  check returns `[]`, Plan dialog says "OK" while its own X–Z preview draws
  the press line through the silhouette. Recorded in CLAUDE.md Known
  Technical Debt (🔴), PROJECT_PLAN §6, TODO, and the disclosure draft.
- Other approach findings recorded as debt/TODO: no Emergency Stop and no
  safe-cancel (heaters stay on, head stays put); Home/Level Bed/Z Calibrate
  block the Tk main thread; `connect` not idempotent + no Disconnect; insert
  sequence invisible while running (no phase callback, live view frozen at
  the sentinel line); plain-line streaming has no resend recovery; opt-in
  `M420 S1` re-send after `G28` still unbuilt; Plan dialog defaults seat Z to
  the part top; "run finished" logs a raw dict.
- GUI/UX findings (from the renders): left column empty below ~60 % height;
  3D view mostly blank in Global mode with overlapping Z tick labels; no
  phase-colour legend anywhere; gray-on-gray captions below WCAG contrast;
  Settings and Z-cal dialog text double-wrapped (embedded newlines +
  `wraplength`); width-4 jog buttons, no arrow-key jog, no tooltips/shortcuts;
  Pause and Resume as two buttons; Abort beside Success and Cancel
  unconfirmed; one default font, no hierarchy. All listed in `TODO.md` as a
  future UX pass.
- **Patent draft (`docs/INVENTION_DISCLOSURE_DRAFT.md`) updated**, owner
  approved all seven items: Q14/Q15/Q17/Q26/Q27 brought to the real state
  (225 tests, serial link + real print verified on hardware, magnet flow
  still sim-only); Q7 gained B10 (planner/preview, preview-equals-execution)
  and B11 (firmware-pause substitution); Q8 notes the collision check; Q9
  gained items 7–9 (toolpath collision check, pause substitution,
  preview-equals-execution); Q11 gained the offset-Z-sign trade-off,
  deployable-pole variants and the pocket-near-edge variant; Q14's worked
  example is now the actual per-phase G-code table lifted from
  `insert_magnet.py` plus a note that the baseline example itself collides;
  Q18 gained claims 7–10; Q21 gained offset-Z sign/ranges, safe-lift
  clearance, open-loop press + proposed over-travel; Q16 re-confirmed
  2026-09-16 — owner states the GitHub remote is private (an
  unauthenticated API probe returned 403, inconclusive, so the owner's word
  is the record).
- Doc fixes in the same commit: `project/PROJECT_PLAN.md` line 116 said
  `seat_z + offset.z` (wrong sign vs. code/CLAUDE.md, fixed + explained);
  `project/BUILD_PLAN.md` C2 acceptance line had the same sign; stale test
  counts in PROJECT_PLAN (94), HOW_IT_WORKS (94) and CLAUDE.md debt (185)
  → 225. `python -m pytest` 225/225 before and after (docs only).
- Owner added three asks mid-session, recorded in `TODO.md`: (1) fewer
  Tkinter windows — the separate Toplevels (Plan, Animate, 3D, Settings,
  Z-cal), each with its own matplotlib canvas, may be why the system feels
  slow; likely contributors are the Animate window's 40 ms tick and the main
  panel's full `Axes3D` redraw every 150 ms during a run → fold into a
  `ttk.Notebook`, redraw only visible tabs, profile the 3D redraw; (2) the
  3D live view does not move during the magnet-insert phase — confirmed
  cause is line-progress-derived position freezing at the sentinel → drive
  the markers from `plan_insert_moves` via the `on_phase` callback; (3) the
  insert planner/runtime must raise explicit errors for any motion that
  could damage the printer or part — nozzle into the build plate, nozzle or
  applicator into the printed part, pocket outside the bed, impossible
  coordinates — same check feeding the dialog and the run.
- Committed as `0de34e1` (docs only).

## 2026-09-16 (cont.) — C25: nozzle-vs-part collision guard + Emergency Stop

- Owner: "go, start C25 with the collision checks and e-stop".
- `sequences/geometry.py` — `check_envelope(mi, config, saved, toolpath=None)`
  is now the single damage guard (Dev Rules 7 + 12): pocket XY on the bed
  (previously a pocket off the bed with a nozzle target on it passed); nozzle
  approach/shear/safe-Z inside the machine limits; `press_z < 0` → "nozzle
  would hit the build plate"; and, with the toolpath, `_part_collisions` —
  the nozzle at PRESS or at 10 points along SHEAR inside the part's bounding
  box (+ `collision.footprint_margin_mm`) while `press_z < saved.z +
  collision.nozzle_clearance_mm` → "nozzle would enter the printed part during
  …" with the numbers and the fix. Bounding-box footprint on purpose
  (conservative; per-layer occupancy is a TODO). New required
  `config.collision.*` keys.
- Wired everywhere the file is known: `insert_magnet(..., toolpath=)`,
  `Controller._on_sentinel` (cached toolpath), `entry.run_headless` (parses
  one best-effort so headless is guarded too), `plan_dialog.envelope_report`,
  `viz/preview.PreviewWindow`. Dialog status reads "UNSAFE — cannot save:"
  with a bullet per reason; Save disabled.
- **The test fixture was the collision case.** `tests/data/sample.gcode`'s
  first extrude started at the origin (after `G28`), so its footprint was
  0..80 and the pocket at X60 with the default +30 mm offset put the nozzle at
  X30 *inside* the part — every Controller/entry test would have failed the
  new guard, correctly. Fixed the fixture (first XY move is now a travel; part
  spans X 40..80), and `test_workflow_sim` uses a −25 mm X offset for the cura
  coupon (spans 0..50). Line count 26 → 29; no test depended on it.
- `Controller.emergency_stop()` — cancels the runner, puts `"abort"` on the
  answers queue if the worker is blocked in `_prompt` (new `_prompt_pending`
  flag), writes `M112` with `send_line` (no idle guard, no `_printer_lock`,
  no `wait_ok` — the worker may hold the lock in `wait_ok` for 30 s), sets
  `estopped`, emits an `error` with the recovery steps. `refresh_state` is a
  no-op while `estopped` (caught during the GUI check: the 2 s idle poll would
  otherwise log a `PrinterError` against the halted board every tick);
  `connect()` clears it. `SimPrinter` models `M112` (heaters 0, `halted`,
  later lines raise `PrinterError`) and `M999`. Red **EMERGENCY STOP**
  `tk.Button` top-right of the panel (ttk ignores `bg` on Windows), always
  enabled, no confirm.
- Tests 225 → 245 (`test_geometry` +9, `test_app` +6, `test_config` +2,
  `test_insert_magnet` +1, `test_printer_sim` +1, `test_plan_dialog` +1,
  `test_workflow_sim` +1). `py_compile` clean; `python main.py --sim --no-gui
  tests\data\sample.gcode --confirm success` exits 0.
- Verified in the real panel via the PrintWindow render of our own windows:
  Plan dialog with pocket X75 Y50 on the sample → red "UNSAFE" with the full
  reason, Save disabled, the X–Z preview showing the press line through the
  silhouette; EMERGENCY STOP pressed mid-run → run stopped, `estopped` True,
  recovery message in the log, and the sequence's error-handler `M104` refused
  by the halted sim exactly as a real board would (logged, not raised).
- Docs synced: `.CLAUDE/CLAUDE.md` (status, module rows, Key Modules for
  geometry/insert_magnet/app/panel, Key Conventions, Dev Rule 12, Known
  Technical Debt — collision + e-stop struck through with the remaining
  limits listed), `project/BUILD_PLAN.md` (Phase 1.12 / C25), `README.md`,
  `TODO.md`, `project/PROJECT_PLAN.md` (§6, risks, status),
  `project/HOW_IT_WORKS.md` (§5), `docs/INVENTION_DISCLOSURE_DRAFT.md`
  (Q8/Q14/Q27: check now implemented).
- Still open from the review: safe-cancel routine, insert-phase live view,
  window/performance consolidation, UX pass, hardware bench-test of `M112`
  (`EMERGENCY_PARSER` on the stock board unverified).

## 2026-09-16 (cont.) — C26: insert-phase live view *(backfilled 2026-09-18 from `project/BUILD_PLAN.md` + git; commit 3f49ca4, 09:56)*

- Problem from the 2026-09-16 review: the panel's live view derives the nozzle
  position from G-code line progress, which freezes at the sentinel for the
  whole magnet insert.
- `sequences/insert_magnet.py` — new keyword-only `on_phase(phase, position)`
  callback, fired once per phase (`PARK`, `DISPENSE`, `APPROACH`, `PRESS`,
  `SHEAR`, `LIFT`, `CONFIRM`, `RESUME`) right before that phase's `_send`,
  with the exact target already computed for it (`None` for the two
  non-motion phases); re-fires on every retry iteration except `PARK`.
- `app.Controller` — `in_insert` property; `_on_sentinel` passes
  `on_phase=self._on_insert_phase`, which emits a new `"phase"` event on the
  existing queue. `viz/toolpath_fig.update_live_3d_marker` factored out so the
  3D marker can move without touching the growing path. `ui/panel.py
  _sync_live_view` follows the phase position while `in_insert`, keeps the 2D
  layer and 3D path frozen at the sentinel, shows the phase as the current
  step; reverts to line-progress the moment `in_insert` is false.
- Tests 245 → 248 (`test_insert_magnet` +2, `test_app` +1). Manual: drove the
  real panel through Tk's event loop across a sentinel insert; label tracked
  PARK → DISPENSE → APPROACH → PRESS → CONFIRM, no draw exceptions.

## 2026-09-16 (cont.) — C27: safe-cancel retreat; Home / Level Bed / Z-cal off the main thread *(backfilled 2026-09-18; commit a46bb79, 10:13)*

- `Controller.cancel()` now spawns `_safe_cancel_retreat`: bounded
  `worker.join`, skip (with a log line) if the worker is still alive — e.g.
  blocked in an insert's operator prompt — otherwise, unless `estopped`,
  retract, lift to `min(z + park.safe_z_lift_mm, machine.z_max)`, park at
  `park.{x,y}`, and `M104 S0`/`M140 S0` if new `config.cancel.heaters_off`
  (default `true`).
- New `_busy` flag / `busy` property and `_run_offline(fn)`; `home()`,
  `level_bed()`, `start_z_calibration()` run on a daemon thread under
  `_printer_lock` instead of blocking Tk; every idle-only guard widened to
  `running or _busy`. `nudge_z`/`save_z_offset` stay synchronous on purpose.
- `set_temp`/`refresh_state` switched to a bounded `acquire(timeout=0.3)` so a
  long background `G28`/`G29` cannot relocate the freeze onto them; suite run
  3× with no flakes.
- Regression found and fixed: four existing tests asserted on `printer.sent`
  right after the now-backgrounded calls; they wait on `not ctl.busy` first.
- Tests 248 → 251. Manual: `home()` returned in ~1 ms; cancel mid-run produced
  the retract/park/heaters-off sequence.

## 2026-09-16 (cont.) — C28: idempotent connect + Disconnect toggle *(backfilled 2026-09-18; commit 8f6b352, 10:20)*

- `Controller.connect()` is a no-op (logs "already connected") when
  `_connected and not _estopped`; the `estopped` carve-out keeps a post-e-stop
  Connect working (it only clears the flag, never reopens the port) — caught
  by the existing C25 test `test_reconnect_clears_estopped` when the first
  pass broke it. Whole body now try/excepts link errors into an `error` event.
- New `disconnect()` — idempotent, refused while `running`/`busy`; printer and
  dispenser closed independently.
- `ui/panel.py` — single Connect ↔ Disconnect toggle (`_toggle_connect`),
  label refreshed every poll, disabled while `busy`.
- Tests 251 → 254 (`test_app` +3). Manual: button read Connect → Disconnect →
  Connect through Tk's event loop, tracking `Controller.connected`.

## 2026-09-16 (cont.) — C29: opt-in line-numbered streaming + resend buffer; `M420 S1` after `G28` *(backfilled 2026-09-18; commit 6ad4b3e, 10:30)*

- Both flags **opt-in, default off**, unverified on the real firmware:
  `gcode.use_line_numbers` and `gcode.resend_leveling_after_home`.
- `gcode/util.py` — `build_numbered_line` (`N<n> text*<xor>`) and
  `strip_line_number` (unconditional, both links accept either format).
- `GcodeRunner` — `M110 N0` once, then `_send_numbered` → `_send_and_resolve`
  with a 64-line `{n: text}` buffer replayed from the requested line on
  `ResendRequested`, recursively under one lock acquisition; an evicted line
  is still fatal. With the leveling flag, `M420 S1` is sent right after any
  streamed `G28` — the automated fix for the 2026-09-15 first-layer root
  cause. With both flags off `_transmit` is byte-for-byte the old path.
- Tests 254 → 260 (`test_runner` +6 incl. a 66-line fixture to force
  eviction; `test_printer_sim` +1). Manual: headless sim run with both flags
  via a throwaway `config.local.yaml` logged "re-sending M420 S1 after G28".

## 2026-09-16 (cont.) — C30: collision footprint restricted to already-printed layers *(backfilled 2026-09-18; commit c8d4627, 10:36)*

- `_part_collisions` used the whole-file bbox, over-refusing a pocket whenever
  the part gets wider above the insert layer. New `geometry._printed_footprint
  (toolpath, printed_top_z, margin)` unions only the extruding segments in
  layers `0 .. layer_for_z(saved.z)`; falls back to `part_footprint` if none.
  Always a subset of the whole-file box, so the change can only stop flagging
  material that does not exist yet. Full per-layer polygon occupancy
  deliberately scoped out (risk of a subtly wrong implementation being less
  safe than the bbox) — stays a TODO.
- Docstrings + CLAUDE.md Known Technical Debt rewritten to the narrower scope.
- Tests 260 → 262 (`test_geometry` +2: wide-layer-above-insert accepted, real
  printed collision still refused).

## 2026-09-16 (cont.) — C31: Animate tick stops when idle, 3D redraw throttled, UX pass *(backfilled 2026-09-18; commit ff0e072, 10:49)*

- Owner: "the system feels slow". Two measured causes fixed:
  `viz/preview.PreviewWindow._tick` no longer reschedules itself unless
  `self.playing` (0 ticks before Play, flat for 2 s after pausing, verified
  with a counting wrapper); new `ui.live3d_poll_s` (0.3 s) gates the 3D
  update + `draw_idle()` to every Nth 2D tick.
- UX: Pause/Resume as one toggle (`Controller.paused`); human-readable "run
  finished: N/M lines sent, K magnet insert(s)"; 3D view defaults to Local;
  Plan dialog seat-Z defaults to the chosen insert layer's height (was the
  file top); double-wrapped labels fixed in Settings/Z-cal; bigger jog buttons
  + arrow/Page keys (ignored while a text entry has focus or busy/running).
- `ttk.Notebook` consolidation of the separate Toplevels explicitly descoped
  (large rearchitecture, no GUI test coverage) — stays in `TODO.md` with the
  rest of the screenshot-review items.
- Tests unchanged at 262 (Tkinter classes are hand-verified through the real
  event loop by project convention).
- Docs synced for C26–C31 in each commit: `.CLAUDE/CLAUDE.md`,
  `project/BUILD_PLAN.md` (Phases 1.13–1.18), `README.md`, `TODO.md`,
  `project/PROJECT_PLAN.md`. **This log was not updated in those six
  sessions** — entries above reconstructed on 2026-09-18.

## 2026-09-18 — Patent disclosure draft refreshed to the C31 state + formatting pass

- Owner asked for a read of the whole project and an update of
  `docs/INVENTION_DISCLOSURE_DRAFT.md` — add anything missing, then format it
  properly. Proposed the change list first (PROJ_STARTER rule), owner approved.
- Gap found: the draft's last refresh was `0de34e1` (2026-09-16, between C24 and
  C25); C25 was partly reflected, C26–C31 not at all, and the test count was
  stale in four places (225/245 vs. 262 — re-ran `python -m pytest`, 262 pass).
  Re-extracted the 27 questions from the K&K `.docx` (zipfile + regex, no
  python-docx in the venv) to confirm the draft still mirrors the form; checked
  the Q14 per-phase G-code table line by line against
  `sequences/insert_magnet.py` — still exact.
- Content changes: Q2 solution mentions the printed-so-far damage guard; Q3 two
  extra search terms; Q5 host-software line notes e-stop/cancel/progress viewer
  as prior art; Q7 rewritten as two tables, new B12 (emergency stop), B13 (safe
  cancel), B14 (run transcript), B15 (opt-in numbered/checksummed streaming +
  `M420 S1` after `G28`), B4/B5/B7 reworded (C26/C30); Q8 step 5 restricted to
  printed layers, step 3 notes the no-polling live view, new step 9 on failure
  paths; Q9 item 7 and Q18 claim 7 sharpened to the printed-so-far footprint,
  item 9 / claim 9 gained the per-phase target reporting, plus an explicit
  "not claimed as novel" line for the standard host features; Q10 host-side
  safety bullet; Q11 collision-check variants; Q12 notes `main.py --preview`
  and the panel can already export the method figures; Q14 validation list and
  a C30 note on the worked example; Q15 test coverage list updated, no hardware
  since 2026-09-15 stated; Q16 "no change known as of 2026-09-18" with a
  `[VERIFY]`; Q17/Q26/Q27 to C31; Q18 dependent claims gained bbox-vs-polygon
  footprint, shear sampling, e-stop-releases-prompt; Q19 row 5 for host
  software; Q21 split into mechanical / insert motion / damage guard /
  communication tables with clearance, margin, shear samples, park, travel,
  prime, ack timeout, resend buffer, Uno settle added.
- Formatting: metadata table (form, status, last updated, sources), placeholder
  legend, contents table linking Q1–Q27, headings normalised to `## Q<n>.`,
  Q22 company slots 1–5 as on the form, closing "Open items checklist" that
  gathers every placeholder by owner (inventors vs. agent).
- Deliberately not done: no web/patent search (offered as optional, not taken
  up); repo-privacy for Q16 not re-verified by me — owner's 2026-09-16 word
  stands, flagged `[VERIFY]`.
- Companion files: this entry; `TODO.md` Done line. Noted for the owner: this
  log has no entries for the C26–C31 sessions although they are committed
  (`3f49ca4` … `ff0e072`) — offered to backfill from `project/BUILD_PLAN.md`.
- Docs only; `python -m pytest` 262/262 before and after.

## 2026-09-18 (cont.) — Log backfill for C26–C31; informal patent search written up

- Owner: "yes backfill the log entries for C26-C31. and run the web/patent
  search and give me a document."
- Backfilled six dated entries above (one per chunk, marked *backfilled*,
  with commit hash and time) from `project/BUILD_PLAN.md` Phases 1.13–1.18
  and `git log`.
- Ran an informal prior-art / patent search (general web search + the Google
  Patents record of each candidate: abstract, claim 1, embodiments, status).
  Written up as **`docs/PRIOR_ART_PATENT_SEARCH.md`** — headline findings,
  a closest-first patent table with overlap/difference per reference, new
  non-patent art, exclusions, what was *not* found, agent recommendations,
  and every source URL.
- Key results: (1) **Stratasys US 8,070,473 B2 / US 7,917,243 B2 / EP
  2 231 375 B1** (2008; active to 2028–2029) claim a controller-driven insert
  placement apparatus on a layer-based printer, incl. embodiments on the
  extrusion head and a tape+roller that presses inserts during deposition —
  the closest patent, must be claim-charted, Indian family unknown; (2)
  **EmGi's Magnet Insertion Tool v1/v2** (2024) is a hand-held magazine +
  magnetic-tip magnet placer — weakens disclosure novelty item 4 on its own;
  (3) pause-insert-resume is a claimed step in several recent patents
  (Honeywell 2024, Univ. of Texas 2020, Markforged 2017), all manual; (4) no
  hit for a G-code comment sentinel, printer-motion press + lateral shear
  from a passive magnetic holder, an offset-tool guard from the printed-so-far
  toolpath, any Indian filing, or any OctoPNP patent. Limits stated in the
  file: no Espacenet / PATENTSCOPE / InPASS, no citation walk, claims read via
  page summaries.
- Disclosure draft updated to match: Q5 patent block, Q6 and Q9 caveats, Q19
  rewritten intro + rows 6–7, Q27 two new engineering risks (ferromagnetic
  nozzles; patterned bed-plate re-polarisation, from Hackaday 2026-06-04),
  agent checklist item to claim-chart the Stratasys family. Risks added to
  `project/PROJECT_PLAN.md` §7; pointer + nozzle-ferromagnetism bullet in
  `project/RESEARCH.md`; new file listed in `README.md` and `.CLAUDE/CLAUDE.md`
  Data Files; `TODO.md` patent item updated.
- Kept as a repo Markdown file rather than a shared web page on purpose — the
  material is confidential disclosure content. Docs only; 262/262 tests.
