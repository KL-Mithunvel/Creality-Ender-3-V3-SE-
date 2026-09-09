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

