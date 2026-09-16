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
- [ ] Hardware decision (from the C25 guard): with a pole-above-nozzle offset the pocket
      must sit within the X/Y offset of a part edge — decide deployable pole vs.
      pocket-near-edge design (`project/PROJECT_PLAN.md` §6, disclosure Q11). Also measure
      the applicator's lowest point vs. the nozzle tip and fold it into
      `collision.nozzle_clearance_mm` if it hangs lower; bench-test EMERGENCY STOP with a
      long move in flight (is `EMERGENCY_PARSER` on in the stock V3 SE firmware?)
- [ ] Collision guard refinement: true per-layer concave/polygon occupancy instead of a
      bounding box over the printed-so-far layers (C30 narrowed the box to only what's
      actually printed at insert time, but an L-shaped *printed* cross-section is still
      treated as its enclosing rectangle)
- [ ] Animate the Animate window's "Open 3D view" (still static) — the main panel's live view
      already tracks the insert phase (C26, below); the separate Animate popup's 3D view doesn't
- [ ] Performance / window sprawl (owner-observed "system feels slow"): Plan, Animate, 3D,
      Settings, Z-cal each open a separate Toplevel with its own matplotlib canvas, and the
      Animate window redraws every 40 ms while open; the main panel redraws two canvases
      (one full `Axes3D` redraw) every 150 ms during a run. Fold the dialogs into a
      `ttk.Notebook` in the main window (one figure per tab, created lazily, redraw only
      when visible), stop the Animate tick when not playing, and profile the 3D
      `draw_idle` — consider redrawing 3D at a slower rate than 2D or blitting
- [ ] Insert-phase polish: a log line per phase (not just the live-view label, C26) and a
      planned-path overlay on the 2D view during an insert (the 2D layer currently just
      freezes and the marker jumps to each phase's waypoint)
- [ ] Bench-test C29's opt-in `gcode.use_line_numbers`/`gcode.resend_leveling_after_home`
      on the real V3 SE before ever enabling them for a real print (checksum/resend format
      and `M420 S1` behavior are both unverified against the real firmware)
- [ ] GUI/UX pass (from the 2026-09-16 screenshot review): fill the empty left column, default
      the 3D view to Local + cap Z ticks, phase-colour legend in Plan/Animate, WCAG-contrast
      captions, fix double-wrapped dialog text, larger jog targets + arrow-key jog + tooltips,
      Pause/Resume as one toggle, separate/confirm destructive actions, `ttk.Style` font +
      semantic status colours, human-readable "run finished" line, Plan dialog seat-Z default
      below the insert layer

## Done

- [x] **Phase 1.17 — C30** (`project/BUILD_PLAN.md`) — collision guard restricted to
      already-printed layers: `geometry._printed_footprint` builds the part-collision box
      from only the segments in layers `0 .. layer_for_z(saved.z)`, not the whole file, so
      a pocket no longer gets refused over geometry that hasn't been printed yet (still a
      bounding box, not true concave occupancy — see the remaining TODO item above). 262 tests.
- [x] **Phase 1.16 — C29** (`project/BUILD_PLAN.md`) — streaming reliability, both opt-in
      and off by default: `gcode.use_line_numbers` makes `GcodeRunner` send
      `N<n> ...*<checksum>` lines and replay a 64-line buffer on a firmware `Resend:`
      instead of aborting the run; `gcode.resend_leveling_after_home` re-sends `M420 S1`
      after any streamed `G28` (the automated fix for the first-layer-quality root cause
      noted 2026-09-15). `printer_sim.py`/`printer_serial.py` both accept either wire
      format. 260 tests.
- [x] **Phase 1.15 — C28** (`project/BUILD_PLAN.md`) — Connect/Disconnect: `Controller.connect()`
      is idempotent (a no-op while already connected and not `estopped`, so it still clears
      `estopped` after a power-cycle without reopening the port); new `disconnect()`
      (idempotent, refused while running/busy); the panel's Connect button is now a
      Connect ↔ Disconnect toggle. 254 tests.
- [x] **Phase 1.14 — C27** (`project/BUILD_PLAN.md`) — safe-cancel + off-thread one-off
      commands: `Controller.cancel()` now retracts/lifts/parks/turns heaters off (config
      `cancel.heaters_off`) once the worker actually stops; `home()`/`level_bed()`/
      `start_z_calibration()` run on a background thread (`_run_offline`) instead of
      blocking the Tk main loop, guarded by a new `busy` property; `set_temp`/
      `refresh_state` switched to a short bounded lock wait so they can't relocate the
      same freeze onto themselves. 251 tests.
- [x] **Phase 1.13 — C26** (`project/BUILD_PLAN.md`) — insert-phase live view:
      `insert_magnet(..., on_phase=)` fires once per phase with its exact nozzle-tip
      target; `Controller.in_insert`/`_on_insert_phase` feed a new `"phase"` event;
      the panel's live view tracks it instead of freezing at the sentinel line during
      a magnet insert. 248 tests.
- [x] **Phase 1.12 — C25** (`project/BUILD_PLAN.md`) — 🔴 damage guard: `geometry.check_envelope`
      now refuses, with the reason, a pocket off the bed, a nozzle target out of range, a
      press into the build plate, and — using the toolpath — a press/shear that would drive
      the nozzle into the printed part; the Plan dialog, preview, headless run and GUI run
      all use it (`config.collision.*`). Red **EMERGENCY STOP** button → `Controller.
      emergency_stop` (`M112` immediately, no lock/guard; unblocks a pending prompt; sim
      models the halt + `M999`). Fixture `sample.gcode` made collision-free. 245 tests.
- [x] **Phase 1.11 — C24** (`project/BUILD_PLAN.md`) — two-column full-screen panel
      (jog/temperature/filament left, live view + send-G-code + log right, both
      stretching to fill a maximized window — `run_gui()` opens `zoomed` by default);
      fixed the 3D view's "extreme Z gaps" with explicit tight axis limits; added a
      "Global bed" / "Local part" 3D crop toggle (Local makes a short/flat part ~2.7x
      more prominent in the box, confirmed via `set_box_aspect`). 225 tests.
- [x] **Phase 1.10 — C23** (`project/BUILD_PLAN.md`) — 2D + 3D live views shown side by
      side (no more toggle); 3D view gained the full bed plate, true equal-mm-per-axis
      scaling (`set_box_aspect`), and a path that grows progressively as the nozzle
      passes through it instead of showing the whole part upfront; fixed a real
      matplotlib bug found along the way (`Line3D` needs numpy arrays, not plain lists);
      panel further compacted (smaller plots, shorter log) — content height 1185px ->
      942px. 224 tests.
- [x] **Phase 1.9 — C22** (`project/BUILD_PLAN.md`) — GUI usability pass from real driving
      feedback: mode/port label (`Controller.link_summary`) next to the connection status,
      the whole panel wrapped in a scrollable canvas (nothing clips on a short screen
      anymore), calibration buttons captioned to explain Level Bed vs. Z Calibrate, the
      live view redraws ~6-7x faster (0.15 s vs. 1.0 s) for smoother motion, and an
      embedded live insert-motion preview in "Plan magnet insert…" (phase-coloured path,
      updates on every keystroke). 223 tests.
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
- [x] Patent draft refresh (2026-09-16): stage/validation/test counts updated, B10/B11
      components, actual per-phase G-code as the worked example, collision-aware check +
      pause-substitution + preview-equals-execution as claim directions, deployable-pole and
      pocket-near-edge embodiments, offset-Z sign/press over-travel in the ranges table,
      repo confirmed private for Q16.
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
