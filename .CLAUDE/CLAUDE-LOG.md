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
