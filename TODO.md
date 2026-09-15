# TODO

Phased plan for the Ender-3 V3 SE magnet-embedding print assistant.
**Authoritative plan: `project/PROJECT_PLAN.md`** (goals, steps, files, success
criteria, risks). Architecture and rules: `.CLAUDE/CLAUDE.md`. Keep all three in sync.

## In Progress

- [ ] Hardware: build the clip-on applicator (magazine + escapement + holding pole + mount);
      wire the Arduino Uno + servo; measure `magnet_tool_offset`; run the manual smoke test
- [ ] Hardware: bench-test the "Z Calibrate…" workflow (C21) on the real printer before
      trusting it on a real print — verify homing/travel, nudge direction and feel, and
      that `M851`/`M500` actually take effect (measure the printer's real starting M851 Z
      value once and set `zcal.probe_z_offset` in `config.local.yaml` before the first run)
- [ ] Patent: fill the `[INVENTORS TO COMPLETE]` sections of `docs/INVENTION_DISCLOSURE_DRAFT.md`,
      run a prior-art search with the K&K agent, confirm college IP policy

## Done

- [x] **Phase 1.9 — C22** (`project/BUILD_PLAN.md`) — GUI usability pass from real driving
      feedback: mode/port label (`Controller.link_summary`) next to the connection status,
      the whole panel wrapped in a scrollable canvas (nothing clips on a short screen
      anymore), calibration buttons captioned to explain Level Bed vs. Z Calibrate, the
      live view redraws ~6-7x faster (0.15 s vs. 1.0 s) for smoother motion, a "3D view"
      isometric toggle, and an embedded live insert-motion preview in "Plan magnet
      insert…" (phase-coloured path, updates on every keystroke). 223 tests.
- [x] **Phase 1.8 — C21** (`project/BUILD_PLAN.md`) — "Z Calibrate…" guided paper-test
      Z-offset dialog (`ui/zcal_dialog.py`); config (`zcal.*`) is the trusted offset,
      not a printer readback; `M851`+`M500` on save. **Untested on real hardware —
      bench-test deliberately before trusting it.** Also confirmed (no code needed)
      that mid-print temp polling + temp changes were already done. 218 tests.
- [x] **Phase 1.7 — C20** (`project/BUILD_PLAN.md`) — embedded live-print view in the
      main panel: current layer + a nozzle-position marker + a current-step G-code
      text readout, driven from G-code line progress against the parsed toolpath
      (no extra printer traffic); 209 tests.
- [x] **Phase 1.6 — C13–C19** (`project/BUILD_PLAN.md`) — 170 tests:
      C13 root `main.py` + `magnet_embed/entry.py` + `Controller.send_command`;
      C14 `gcode/toolpath.py`; C15 `sequences/geometry.py` (`plan_insert_moves` /
      `check_envelope`); C16 `viz/` matplotlib toolpath + insert-motion preview
      (`main.py --preview`); C17 `ui/plan_dialog.py` (place sentinel + save
      `*.magnet.gcode`); C18 idle poll + extrude/retract + progress bar;
      C19 end-to-end workflow test + `GcodeRunner` drops `M0`/`M1`/`M25`/`M600`/`M601`.
- [x] Write `project/HOW_IT_WORKS.md` (plain-language system walkthrough).
- [x] Draft `docs/INVENTION_DISCLOSURE_DRAFT.md` from the K&K form (27 answers + gaps marked).

- [x] Scope printer-control options and pick a direction — Python host script (`pyserial` /
      `printrun.printcore`) + Tkinter panel; PC tethered over USB-C, no Raspberry Pi.
- [x] Settle the mechanism — clip-on applicator; Arduino Uno drives one servo that
      dispenses a magnet to a holding pole; the printer presses (Z) and shears (lateral);
      operator confirms Success / Retry / Abort; no `G28` mid-print.
- [x] Fill in `.CLAUDE/CLAUDE.md` with the real project brief; populate this file and README.
- [x] Write `project/PROJECT_PLAN.md` (mechanism, insert state machine, Uno protocol,
      phases, risks, open questions); add `.gitignore`.
- [x] Research host G-code streaming + write `project/BUILD_PLAN.md` (chunks C1–C6, protocol notes, references).
- [x] **C1** — package scaffold, `config` loader, `SimPrinter`, `SimDispenser`, sentinel
      parser, `GcodeRunner`, headless `main_sim`; 33 tests pass.
- [x] **C2** — `sequences/insert_magnet.py` full SAVE…RESUME state machine (M400-gated,
      envelope check, retry/abort, temp + position + mode restore); 44 tests pass.
- [x] **C3** — `gcode/postprocess.py` + CLI (Cura + PrusaSlicer marker parsing,
      sentinel injection by layer or Z height); 56 tests pass.
- [x] **C4** — `app.Controller` (threaded mediator) + `ui/panel.py` Tkinter control
      panel + modal Success/Retry/Abort prompt; `main_sim --gui`; 64 tests pass.
- [x] **C5** — `links/_marlin_rx.py` + `SerialPrinter` + `SerialDispenser` + `main.py`
      + `--ping` CLIs, tested via an injected fake serial; 91 tests pass.
- [x] **C6** — `runlog.py` (per-run transcript), config numeric/type validation,
      end-to-end integration test, full sanity checklist. 94 tests. Fixed a `RunLog`
      RLock deadlock found by the integration test. **Phase 1 software complete.**
- [x] **C7** — `magnet_embed/main_printer.py` printer-only entry point (real
      `SerialPrinter`, `dispenser=None`); `--ping`. Stream a real print with no Uno.
      98 tests.

## Not Started

### Phase 0 — mechanical proof (no host code)
- [ ] Model a test coupon with a magnet pocket (press-fit undercut, seal cap on top)
- [ ] Slice with slicer pause-at-layer (`M0`), seat a magnet by hand, resume
- [ ] Verify cap bonding, magnet capture, pull strength
- [ ] Choose retention strategy (press-fit / + adhesive / passive stripper)
- [ ] Record magnet grade / dimensions / pocket clearance / bed-attraction in PROJECT_PLAN §8

### Phase 1 — Python host + Tkinter (operator-triggered steps)
Chunked in `project/BUILD_PLAN.md` — one commit per chunk.
- [x] C1 Skeleton: config, `SimPrinter`, sentinel parser, `GcodeRunner`, headless `main_sim` + tests (33 pass)
- [x] C2 `sequences/insert_magnet.py` — SAVE…RESUME state machine against the sim + tests (44 pass)
- [x] C3 `gcode/postprocess.py` — `;MAGNET_INSERT X Y Z S<dir>` injection + CLI + tests (56 pass)
- [x] C4 `app.Controller` mediator + `ui/panel.py` Tkinter panel + modal prompt (64 pass)
- [x] C5 `_marlin_rx` + `printer_serial` + `dispenser_serial` + `main.py` + `--ping` CLIs (91 pass)
- [x] C6 `runlog.py` + integration sim test + config type-checks + full sanity pass (94 pass)
- [x] C7 `main_printer.py` printer-only entry point (real printer, `dispenser=None`) + `--ping` (98 pass)
- [x] C8 `main.py --no-dispenser` / graceful dispenser-optional degrade (105 pass)
- [x] C9–C12 folded into Phase 1.6 — raw G-code entry (C13), idle poll + extrude/retract + progress bar (C18)
- [~] Hardware smoke test on the real printer + Uno (manual; needs the applicator)
      - [x] Printer link: `printer_serial --ping` on COM3 — M115/M400/M114 OK (2026-09-09)
      - [ ] Uno link (`dispenser_serial --ping`) — Uno not connected yet
      - [ ] `main.py --ping` — both at once — blocked on the Uno
- [ ] Full hardware print completes with one operator-driven insert

### Phase 2 — magnet applicator (Arduino Uno + printer moves)
- [ ] 2.1 Finalise applicator mechanics (magazine escapement, pole vs pocket retention)
- [ ] 2.2 Measure `magnet_tool_offset` (with signs); pick `press` + `shear` params
- [ ] 2.3 Arduino Uno sketch (`PING` / `DISPENSE` / `RESET` / `STATUS` + idle watchdog)
- [ ] 2.4 `DispenserLink` + `dispenser_sim`
- [ ] 2.5 `dispenser_serial` (rides out the Uno auto-reset) + `--ping` on real Uno
- [ ] 2.6 Wire `dispenser.dispense()` into the `DISPENSE` state, operator fallback kept
- [ ] 2.7 Bench tests: servo alone, cold air-insert, magnet-near-plate, idle-heater timeout
- [ ] 2.8 End-to-end hardware run: print -> dispense -> press -> shear -> operator OK -> resume
- [ ] 5 consecutive clean coupons, 0 magnets pulled back out
- [ ] Dispenser `ERR` / `WARN IDLE` leaves the printer paused and resumable

### Phase 3 — hardening (later)
- [ ] Nozzle wipe / temp-drop tuning
- [ ] Failure recovery (magazine jam, empty magazine, disconnect mid-pause)
- [ ] Multi-magnet parts (multiple sentinels, per-sentinel park + shear)
- [ ] Optional hall sensor to confirm deposit
- [x] In-panel config editing (`ui/settings_dialog.py` — port + magnet-offset, writes `config.local.yaml`)
- [x] Run log / print report to `logs/` (`RunLog` summary block)
