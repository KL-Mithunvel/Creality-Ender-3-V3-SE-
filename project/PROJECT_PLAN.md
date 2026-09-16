# Project Plan — Ender-3 V3 SE Magnet-Embedding Print Assistant

| | |
|--|--|
| Owner | kl mithunvel |
| Created | 2026-09-09 |
| Updated | 2026-09-16 |
| Status | Phase 1 software complete through C26 (248 tests, see `project/BUILD_PLAN.md`); printer serial link + a real streamed print verified on hardware. Phase 0 (mechanical) and the magnet-flow hardware work not started. **Open design decision:** with a pole-above-nozzle offset the pocket must sit near a part edge (the C25 guard enforces it) — deployable pole or pocket constraint, see §6. |
| Full brief | `.CLAUDE/CLAUDE.md` |
| Task tracker | `TODO.md` |
| Session history | `.CLAUDE/CLAUDE-LOG.md` |

This document is the authoritative multi-phase plan. `TODO.md` mirrors the
checklist; `.CLAUDE/CLAUDE.md` holds the architecture and rules. If the three
disagree, this file and `.CLAUDE/CLAUDE.md` win and the other must be corrected in
the same commit.

---

## 1. Objective & Scope

**Objective.** Print a part on the Ender-3 V3 SE, pause at a known layer, embed a
permanent magnet into a printed pocket, then resume so the remaining layers seal
the part over the magnet — with the operator doing the parts that are not worth
automating yet.

**In scope**
- Host software on the Windows PC that streams G-code to the printer over USB-C.
- A reliable, resumable "pause → insert magnet → resume" sequence.
- G-code post-processing to mark the insertion point and carry the pocket location.
- A simulation path so everything is testable without hardware.
- Phase 2: an Arduino Uno that dispenses one magnet from a magazine per insert.

**Out of scope (for now)**
- Firmware reflashing (Klipper / custom Marlin). The printer stays stock.
- Networked / headless operation, OctoPrint, a Raspberry Pi.
- Fully unattended multi-part production runs.
- Vision / closed-loop verification (a hall sensor is a Phase 3 maybe).
- Magazine auto-refill.
- Z-clearance handling for the add-on during normal printing (see assumptions).

---

## 2. Working Assumptions

- **The applicator is a clip-on add-on.** It clips on and off the toolhead. For now
  assume it **does not hinder normal printing** — no tool-lift servo, and the host
  does not manage nozzle Z-clearance for the add-on. Revisit if this breaks.
- **One magnet per part** for the prototype.
- **The operator is present** for every insert and answers a Success / Retry / Abort
  prompt.
- **The magnet pocket is inside the offset-reachable area** of the bed (see §6).

---

## 3. Mechanism & Locked Decisions

### How a magnet gets embedded

1. **Dispense** — the Arduino Uno drives **one servo** that feeds a single magnet
   from a magazine onto a **holding pole** at the applicator tip. The pole retains
   the magnet by magnetic attraction. This is the *only* job the Uno / servo does.
2. **Approach** — the printer moves so the holding pole (not the nozzle) is over the
   pocket, applying the fixed **magnet-tool offset**.
3. **Press** — the printer drives **Z down** to seat the magnet into the pocket.
4. **Shear** — the printer makes a short **lateral** move so the holding pole slides
   off the seated magnet. Lateral, never straight up: the pocket walls resist the
   magnet moving sideways, so it stays put while the pole peels away.
5. **Ask** — the operator confirms Success, or asks for Retry (they make the area
   safe first), or Abort.
6. **Resume** — printer returns to the saved position and printing continues; the
   next layers seal the magnet in.

### Decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| Control channel | Python host over USB-C serial (`pyserial` / `printrun.printcore`), 115200 | Owner's stack; no reflash; printer still usable standalone |
| UI | Tkinter control panel | PROJ_STARTER default for desktop UI |
| Pause trigger | `;MAGNET_INSERT X Y Z S<dir>` comment injected by `gcode/postprocess.py` | File still prints from microSD; host detects + parses it in the stream |
| Dispenser MCU | **Arduino Uno**, one servo, `PING`/`DISPENSE`/`RESET`/`STATUS` | Simple, on hand; dumb by design |
| Press force | **Printer Z**, open-loop, fixed depth at slow feed (no load sensor on the V3 SE) | Precise depth; tune on coupons |
| Shear | **Printer lateral move**, direction from the sentinel `S` field | Doesn't pull the magnet out; keeps position tracked |
| Re-homing | **None mid-print.** Save state, restore exact coordinates | `G28` mid-print risks a nozzle-through-part crash |
| Topology | Windows PC tethered to the printer over USB-C the whole print. No Pi | Simplest |
| Sim vs hardware | Entry point (`main_sim.py` vs `main.py`), not a code flag | Cleaner; both read one `config.yaml` |
| Config | All ports/coords/temps/offset in `magnet_embed/config.yaml`; local overrides in gitignored `config.local.yaml` | CLAUDE-COMMON rule 3 |

---

## 4. Architecture (summary)

Full detail in `.CLAUDE/CLAUDE.md` → Architecture.

```
slicer ─► part.gcode ─► postprocess (inject ";MAGNET_INSERT X Y Z S<dir>") ─► part.magnet.gcode
                                                                                    │
   ui/panel.py ─► gcode/runner.py ─► links/printer_serial ──USB-C──► Ender-3 V3 SE
                        │                                            (press + shear = printer moves)
        on sentinel: sequences/insert_magnet  (SAVE…RESUME state machine)
                        │
                        └─► links/dispenser_serial ──USB──► Arduino Uno ─► magazine servo   [Phase 2]
```

- G-code streaming on a worker thread; Tkinter on the main thread; queue + `root.after()` for UI updates.
- Every hardware link (`printer`, `dispenser`) has a simulated twin with identical return shapes and exceptions.

### Insert state machine

```
SAVE      record X Y Z E, feedrates, G90/G91, M82/M83, nozzle + bed temp (track + confirm M114/M105)
PARK      M83; retract 2–5 mm; Z-hop to safe clearance; nozzle → standby_nozzle_temp_c; bed unchanged
DISPENSE  dispenser.dispense()  (Phase 1: operator prompt "magnet loaded on pole?")  → magnet on the pole
APPROACH  move XY to  pocket_xy − magnet_tool_offset.xy  at safe Z
          host checks the target is in-envelope → on failure: abort, print stays paused
PRESS     Z down to  seat_z − magnet_tool_offset.z  at press.feed;  dwell press.dwell_ms
          (offset = pole tip − nozzle tip, so a pole ABOVE the nozzle means the nozzle goes BELOW the seat)
SHEAR     lateral move  shear.distance  along  shear_dir  at  shear.feed
LIFT      Z to safe clearance;  move clear of the part
ASK       prompt() → "success" | "retry" | "abort"
           retry → operator confirms area safe + whether a magnet is still on the pole
                   → re-enter at DISPENSE (new magnet) or APPROACH (magnet still held)
           abort → nozzle heater off, bed off after abort.bed_hold_min, stay paused (resumable) or cancel
RESUME    nozzle → saved print temp, M109 wait;  move XY → saved pos at safe Z;  Z → saved Z;
          un-retract;  prime prime.mm + wipe;  restore G90 / M82 / feedrates
CONTINUE  hand back to GcodeRunner, stream the next line
```

No `G28` anywhere.

### Dispenser (Arduino Uno) serial protocol

Newline-terminated ASCII. Host waits ~2 s for the Uno's auto-reset after opening the port, flushes, then `PING`s until `PONG`.

| Host → Uno | Uno → Host | Meaning |
|---|---|---|
| `PING` | `PONG` | liveness / post-reset handshake |
| `DISPENSE` | `OK DISPENSE` / `ERR DISPENSE <reason>` | feed exactly one magnet to the pole |
| `RESET` | `OK RESET` | servo to home / loaded position |
| `STATUS` | `STATUS servo=<deg> count=<n> last=<cmd>` | telemetry |
| — | `WARN IDLE` | watchdog fired (no command for ~30 s), servo safed |

---

## 5. Phases

### Phase 0 — Mechanical proof (no host code)

**Goal.** Confirm a magnet can be seated in a printed pocket mid-print and sealed
over, and survives the reheat, before writing software.

**Steps**
1. Model a small coupon with a magnet pocket ~4–6 layers below the top surface.
   Try a slight undercut / taper for a press-fit.
2. Slice (Creality Print / Cura); add a pause at the layer where the pocket is complete
   (`M0` flavour).
3. Print. At the pause, drop the magnet in (by hand or with a dummy pole), press it
   home, resume.
4. Check: cap layers bond cleanly, magnet captured with no rattle, post-print pull
   force within ~20% of a bare magnet.
5. Decide retention strategy: press-fit alone / press-fit + adhesive / passive stripper.
6. Test how strongly a magnet is pulled toward the bare steel flex plate at the pocket depth.

**Files affected.** None (repo). Produces a reference STL/3MF and fills §8.

**Success criteria**
- [ ] Cap layers print cleanly over the magnet (no blob / gap / lifted edge)
- [ ] Magnet mechanically captured, no rattle
- [ ] Post-print pull force within ~20% of a bare magnet of the same grade
- [ ] Retention strategy chosen and recorded in §8
- [ ] Magnet grade + dimensions + pocket clearance recorded in §8
- [ ] Bed-attraction behaviour at pocket depth recorded in §8

---

### Phase 1 — Python host + Tkinter, operator-triggered steps

> Implementation is chunked in **`project/BUILD_PLAN.md`** (C1–C6), one commit per
> chunk, with Marlin serial-protocol notes and research references. The task table
> below is the feature view; BUILD_PLAN is the build order.

**Goal.** A control panel that runs a real sliced file end-to-end, stops at the
sentinel, walks the full insert state machine with **operator prompts standing in
for the Uno**, and resumes — proven in simulation, then on the printer.

| # | Task | Files affected | Success criteria |
|---|------|----------------|------------------|
| 1.1 | Repo scaffold | `magnet_embed/__init__.py`, `magnet_embed/config.yaml`, `requirements.txt`, `tests/` | Fresh venv `pip install` works; `pytest` runs |
| 1.2 | `PrinterState` + `MagnetInsert` + `PrinterLink` abstract | `magnet_embed/state.py`, `magnet_embed/links/printer_link.py` | Interfaces documented; abstract methods raise `NotImplementedError` |
| 1.3 | `printer_sim` | `magnet_embed/links/printer_sim.py` | Consumes a G-code file, tracks X/Y/Z/E + temps, returns `ok`, raises `AckTimeout` / `PrinterConnectionError`; unit-tested |
| 1.4 | `GcodeRunner` | `magnet_embed/gcode/runner.py` | Streams a file against `printer_sim`; `pause`/`resume`/`cancel` thread-safe; on a sentinel-prefixed line, parses `MagnetInsert` and calls `on_sentinel`, does not send it; raises `SentinelNotFound` / `SentinelParseError` |
| 1.5 | `postprocess.py` | `magnet_embed/gcode/postprocess.py` | Injects exactly one `;MAGNET_INSERT X Y Z S<dir>` at the target layer/height; handles Cura + PrusaSlicer markers; CLI validates `--shear`; unit-tested with fixture G-code |
| 1.6 | `insert_magnet` state machine | `magnet_embed/sequences/insert_magnet.py` | Runs SAVE…RESUME against `printer_sim`; envelope check aborts cleanly; `retry`/`abort` paths work; on any exception restores temp, makes no partial move, re-raises (Dev Rule 5); no `G28` (Dev Rule 11) |
| 1.7 | Tkinter panel | `magnet_embed/ui/panel.py`, `magnet_embed/main_sim.py` | Connect, jog/home (disabled mid-print), temps, load G-code, run, pause/resume/cancel, "Insert Magnet", modal Success/Retry/Abort, scrolling log; no Tkinter calls off the main thread |
| 1.8 | Real printer link + smoke test | `magnet_embed/links/printer_serial.py`, `magnet_embed/main.py` | `--ping` returns the firmware banner; a Z-raised air-print with a sentinel near layer 2 runs the whole state machine and completes |

**Pre-hardware gate (before task 1.8 touches the printer).**
`pytest` green · `main_sim.py` runs a real sample file to completion with the state
machine firing · jog/home/temp verified in sim · printer COM port set · magnet-tool
offset in config (rough is fine for the air-print) · stock firmware backup · Windows
sleep disabled.

**Phase 1 done when**
- [x] Simulation: full sample print completes with one operator-driven insert (`test_integration_sim.py`)
- [ ] Hardware: same on the printer, on a Phase 0 coupon, nozzle hot, real filament
- [x] All 1.x success criteria met; tests cover happy path + ack timeout + bad sentinel + out-of-envelope (225 tests as of C24)

> Implementation notes: built as chunks C1–C6 (`project/BUILD_PLAN.md`). Deviations
> from this table: helpers landed in `gcode/util.py`; the UI mediator is a separate
> `app.Controller`; the Marlin reply parser is `links/_marlin_rx.py`; per-run
> logging is `runlog.py`. Real hardware is untouched.

---

### Phase 2 — Magnet applicator (Arduino Uno + printer moves)

**Goal.** Replace the operator's hand at the `DISPENSE` step with the Uno, and prove
the printer-driven press + lateral shear on real parts.

| # | Task | Files affected | Success criteria |
|---|------|----------------|------------------|
| 2.1 | Applicator mechanics | `dispenser_fw/README.md`, §8 | Magazine escapement isolates exactly one magnet against magnet-to-magnet pull; holding-pole strength lets the lateral shear strip the magnet without dragging it out; mounting + offset roughed in |
| 2.2 | Measure the offset + shear params | `magnet_embed/config.yaml`, §8 | `magnet_tool_offset {x,y,z}` measured with sign; `shear.distance` / default `shear_dir` / `press` depth + feed + dwell chosen |
| 2.3 | Arduino Uno sketch | `dispenser_fw/dispenser.ino` | `PING`→`PONG`, `DISPENSE`→`OK`/`ERR`, `RESET`, `STATUS`, idle watchdog → `WARN IDLE` + servo safed; one dispense cycle repeatable by hand test |
| 2.4 | `DispenserLink` + `dispenser_sim` | `magnet_embed/links/dispenser_link.py`, `magnet_embed/links/dispenser_sim.py` | `dispense()` returns on `OK DISPENSE`, raises `DispenserError` on `ERR`; sim mirrors both + the auto-reset delay; unit-tested |
| 2.5 | `dispenser_serial` | `magnet_embed/links/dispenser_serial.py` | `--ping` returns `PONG` against the real Uno after riding out the auto-reset |
| 2.6 | Wire into the state machine | `magnet_embed/sequences/insert_magnet.py`, `magnet_embed/main.py` | When a dispenser is present, `DISPENSE` calls `dispenser.dispense()`; operator prompt stays as the fallback / retry path |
| 2.7 | Bench tests | — | (a) servo alone via serial monitor; (b) cold "air insert" dry-run of APPROACH/PRESS/SHEAR/LIFT to check offset signs + clearances; (c) magnet-near-plate distance; (d) how long the V3 SE holds temp with no G-code before its idle timeout |
| 2.8 | End-to-end hardware run | — | Print → dispense → press → lateral shear → operator OK → resume → sealed part |

**Phase 2 done when**
- [ ] 5 consecutive coupons with automatic dispense + printer press/shear, 0 magnets pulled back out
- [ ] A dispenser `ERR` or `WARN IDLE` mid-print leaves the printer paused and resumable, not crashed
- [ ] Idle-heater timeout behaviour known and handled (keepalive or re-assert temps)

---

### Phase 3 — Hardening (later)

- [ ] Nozzle wipe + temp-drop tuning to kill ooze strings during the pause
- [ ] Failure recovery: magazine jam, empty magazine, serial disconnect mid-pause
- [ ] Multi-magnet parts: multiple sentinels, per-sentinel park + shear direction
- [ ] Optional hall sensor on the pole to confirm the magnet left (replace/augment the operator check)
- [x] In-panel config editing instead of hand-edited YAML (`ui/settings_dialog.py`)
- [x] Run log / print report written to `logs/` (`RunLog` summary block, C-2026-09-15)

---

## 6. Tool Offset & Reachable Area

- The holding pole is offset from the nozzle by `magnet_tool_offset {x, y, z}`
  (measure empirically: jog nozzle to a marked point, jog until the pole is over the
  same point, read the delta; check the **sign of Z** — is the pole above or below
  the nozzle tip).
- To put the pole at bed `(px, py)` the carriage goes to `(px − x, py − y)`. With a
  positive offset, pockets near `X0` / `Y0` push the carriage out of range — so the
  reachable area for the pole is the bed minus a border on two sides.
- `insert_magnet` computes the carriage target, checks it against the machine limits
  from config, and **aborts the sequence (print paused) if out of range** — it never
  commands an out-of-bounds move (Dev Rule 12).
- Keep the magnet pocket well inside the reachable area at design time.
- **Nozzle-vs-part collision (found 2026-09-16, guarded since C25).** With
  the pole tip *above* the nozzle (`offset.z` positive, the current default)
  the nozzle presses to `seat_z − offset.z`, i.e. *below* the seat, at a point
  `offset.xy` away from the pocket — inside the part unless the pocket is
  within the offset distance of a part edge. `sequences/geometry.check_envelope`
  now refuses that (toolpath bounding-box footprint + `collision.*` clearance
  and margin) in the Plan dialog, the preview, and the run — so the software
  is safe, but the **design decision is still open**: constrain pockets to
  within `|offset.x|`/`|offset.y|` of a part edge, or build a deployable pole
  (Q11 of the disclosure draft). Tracked in `TODO.md`.

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| USB tether drops mid-print | Print aborts | Disable Windows sleep; short cable; `GcodeRunner` pauses (not aborts) on serial error, operator reconnects |
| Long pause → nozzle ooze / part shift | Failed layer on resume | Short pause; drop nozzle to `standby_nozzle_temp_c`; wipe before resume (Dev Rule 6) |
| Holding pole stronger than pocket retention | Shear drags the magnet back out | Press-fit pocket + weak pole + optional adhesive; lateral (not vertical) shear; tune on coupons (§8) |
| Magazine clumps, dispenses 0 or 2 | Missed or doubled insert | Escapement isolates one; `DISPENSE`→`ERR` if the servo can't complete; operator check catches it |
| Magnet snaps to the steel flex plate | Magnet lost / plate lifts | Pole holds the magnet until shear; measure safe approach distance in Phase 0/2 |
| Tool offset target out of envelope | Bad move / crash | Host damage guard aborts the sequence, print stays paused (Dev Rule 12) |
| Nozzle driven into the printed part during PRESS/SHEAR (pole above nozzle) | Nozzle-through-part crash | C25 guard refuses it in the dialog, preview and run; pocket must sit near a part edge or the pole must deploy (§6) |
| Runaway during a move / insert | Damage to printer or part | Red EMERGENCY STOP (`M112`, no lock, no idle guard); power-cycle + reconnect afterwards. `EMERGENCY_PARSER` on the stock board unverified |
| Over-deep `PRESS` | Z skips / part damage | Conservative `seat_z`, slow `press.feed`, dwell then retract; tune on coupons |
| V3 SE idle-heater timeout during the pause | Host stalls on resume reheat | Phase 2 test 2.7(d); send `M105` keepalive or re-assert temps |
| Creality serial quirks (`ok` handling, no temp autoreport) | Host stalls | Use `printrun.printcore`; `wait_ok` has a timeout + `AckTimeout` |
| Arduino auto-reset on connect | First commands lost | `dispenser_serial` waits ~2 s, flushes, `PING`s until `PONG` |
| Servo browns out the Uno regulator | Resets / erratic servo | Separate 5–6 V servo supply, common ground |
| Klipper/OctoPrint scope creep | Delays the prototype | Explicitly out of scope §1; revisit only after Phase 2 |

---

## 8. Open Questions & Findings

Fill in as Phase 0 / early Phase 2 progresses.

- Magnet: grade? diameter × thickness? ______
- Pocket clearance / undercut for a reliable press-fit without cracking the wall: ______
- Retention strategy: press-fit only / press-fit + adhesive / passive stripper? ______
- Cap layer count for a full seal: ______
- `magnet_tool_offset` x / y / z (with signs), measured: ______
- Is the holding pole above or below the nozzle tip? ______
- `press`: seat depth, feed, dwell: ______
- `shear`: distance, default direction, feed: ______
- Nozzle standby temp that avoids ooze but resumes fast: ______
- V3 SE: how long does it hold temp with no G-code before the idle timeout? ______
- Magazine escapement mechanism: ______
- Bed-attraction: closest safe pole-to-plate distance at pocket depth: ______
