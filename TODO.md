# TODO

Phased plan for the Ender-3 V3 SE magnet-embedding print assistant.
**Authoritative plan: `project/PROJECT_PLAN.md`** (goals, steps, files, success
criteria, risks). Architecture and rules: `.CLAUDE/CLAUDE.md`. Keep all three in sync.

## In Progress

- [ ] C3–C6 (see `project/BUILD_PLAN.md`)
- [ ] Patent: fill the `[INVENTORS TO COMPLETE]` sections of `docs/INVENTION_DISCLOSURE_DRAFT.md`,
      run a prior-art search with the K&K agent, confirm college IP policy

## Done

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
- [ ] C3 `gcode/postprocess.py` — `;MAGNET_INSERT X Y Z S<dir>` injection + CLI + tests
- [ ] C4 Tkinter panel + threading mediator (Success / Retry / Abort modal)
- [ ] C5 Real serial: `printer_serial` + `dispenser_serial` + Marlin rx parser + tests
- [ ] C6 Integration sim test, run logging, full sanity pass
- [ ] Pre-hardware gate passed
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
- [ ] In-panel config editing
- [ ] Run log / print report to `logs/`
