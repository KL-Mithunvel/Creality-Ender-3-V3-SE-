# Project Plan — Ender-3 V3 SE Magnet-Embedding Print Assistant

| | |
|--|--|
| Owner | kl mithunvel |
| Created | 2026-09-09 |
| Status | Planning — no code yet |
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
- G-code post-processing to mark the insertion point.
- A simulation path so everything is testable without hardware.
- Phase 2: a separate microcontroller that actuates a magnet placer.

**Out of scope (for now)**
- Firmware reflashing (Klipper / custom Marlin). The printer stays stock.
- Networked / headless operation, OctoPrint, a Raspberry Pi.
- Fully unattended multi-part production runs.
- Vision / closed-loop verification that the magnet seated correctly.
- Magnet magazine auto-refill.

---

## 2. Locked Decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| Control channel | Python host script over USB-C serial (`pyserial` / `printrun.printcore`), 115200 | Matches the owner's stack; no firmware reflash; printer stays usable standalone |
| UI | Tkinter control panel | PROJ_STARTER default for desktop UI |
| Pause trigger | `;MAGNET_INSERT` comment injected into the G-code by `gcode/postprocess.py` | File still prints from microSD unchanged; host detects the line in the stream |
| Magnet placement | Phase 1: operator-triggered (button/click). Phase 2: actuated placer on a separate ESP32 / RP2040 (Pico) MCU on a 2nd USB serial port | Keeps Phase 1 simple; automation is an additive step |
| Topology | Windows PC tethered to the printer over USB-C the whole print. No Raspberry Pi | Simplest; owner has no Pi requirement |
| Sim vs hardware | Selected by entry point (`main_sim.py` vs `main.py`), not a code flag | Cleaner than a global boolean; both read one `config.yaml` |
| Config | All ports/coords/temps in `magnet_embed/config.yaml`; local overrides in gitignored `config.local.yaml` | CLAUDE-COMMON rule 3 |

---

## 3. Architecture (summary)

Full detail in `.CLAUDE/CLAUDE.md` → Architecture. In short:

```
slicer ──► part.gcode ──► postprocess (inject ";MAGNET_INSERT") ──► part.magnet.gcode
                                                                          │
   ui/panel.py ──► gcode/runner.py ──► links/printer_serial ──USB-C──► Ender-3 V3 SE
                          │
        on ";MAGNET_INSERT": sequences/insert_magnet
                          │
                          └──► links/placer_serial ──USB──► Placer MCU   [Phase 2]
```

- G-code streaming on a worker thread; Tkinter on the main thread; queue + `root.after()` for UI updates.
- Every hardware link (`printer`, `placer`) has a simulated twin with identical return shapes and exceptions.

---

## 4. Phases

### Phase 0 — Mechanical proof (no host code)

**Goal.** Confirm that a magnet can be dropped into a printed pocket mid-print and
sealed over, and that it survives the reheat, before writing any software.

**Steps**
1. Model a small test coupon with a magnet pocket whose top sits ~4–6 layers below the part's top surface. Pocket sized for a light press / drop fit.
2. Slice in Creality Print or Cura. Add a pause at the layer where the pocket is complete (Cura "Pause at height" → Marlin `M0`, or Creality Print's pause).
3. Print. At the pause, mark magnet polarity, drop it in, press knob to resume.
4. After the print: check the cap layers bonded, the magnet is flush/captured, and its pull strength is acceptable.
5. Repeat with 2–3 magnet grades if the first weakens.

**Files affected.** None (repo). Produces reference STL/3MF + notes added to this file's §7.

**Success criteria**
- [ ] Cap layers print cleanly over the magnet with no blob / gap / lifted edge.
- [ ] Magnet is mechanically captured and does not rattle.
- [ ] Post-print pull force is within 20% of a bare magnet of the same grade.
- [ ] Chosen magnet grade + dimensions + pocket clearance recorded in §7.

---

### Phase 1 — Python host + Tkinter, operator-triggered place

**Goal.** A working control panel that runs a real sliced file end-to-end, stops
at the sentinel, waits for the operator to insert a magnet, and resumes — proven
in simulation, then on the printer.

| # | Task | Files affected | Success criteria |
|---|------|----------------|------------------|
| 1.1 | Repo scaffold | `magnet_embed/__init__.py`, `magnet_embed/config.yaml`, `requirements.txt`, `tests/` | `pip install -r requirements.txt` succeeds in a fresh venv; `pytest` runs (0 tests OK) |
| 1.2 | `PrinterState` + `PrinterLink` abstract | `magnet_embed/state.py`, `magnet_embed/links/printer_link.py` | Interface documented; abstract methods raise `NotImplementedError` |
| 1.3 | `printer_sim` | `magnet_embed/links/printer_sim.py` | Consumes a G-code file, tracks X/Y/Z/E + temps, returns `ok`, raises `AckTimeout`/`PrinterConnectionError` like the real link; unit-tested |
| 1.4 | `GcodeRunner` | `magnet_embed/gcode/runner.py` | Streams a file against `printer_sim`; `pause`/`resume`/`cancel` thread-safe; fires `on_sentinel` on a stripped-line match and does not send it; raises `SentinelNotFound` when required and absent |
| 1.5 | `postprocess.py` | `magnet_embed/gcode/postprocess.py` | `inject_sentinel(..., layer=N)` and `..., z_mm=H)` insert exactly one `;MAGNET_INSERT`; handles Cura (`;LAYER:`) and PrusaSlicer (`;LAYER_CHANGE`/`;Z:`) markers; CLI works; unit-tested with fixture G-code |
| 1.6 | `insert_magnet` sequence | `magnet_embed/sequences/insert_magnet.py` | Parks to `park_xy` at `safe_z_lift_mm`; optional temp drop/restore; calls `confirm()` (Phase 1); restores head to saved position; on any exception restores temp, makes no partial move, re-raises (Dev Rule 5) |
| 1.7 | Tkinter panel | `magnet_embed/ui/panel.py`, `magnet_embed/main_sim.py` | Connect, home, jog ±X/Y/Z, set temps, load G-code, run, pause/resume/cancel, "Insert Magnet", scrolling log; no Tkinter calls off the main thread |
| 1.8 | Real printer link + smoke test | `magnet_embed/links/printer_serial.py`, `magnet_embed/main.py` | `python -m magnet_embed.links.printer_serial --ping` returns the firmware banner; a Z-raised air-print with a sentinel near layer 2 parks, waits, resumes, completes |

**Pre-hardware gate (before task 1.8 touches the printer).** All of:
`pytest` green · `main_sim.py` runs a real sample file to completion with the
sentinel firing · jog/home/temp verified in sim · COM port set in config ·
stock firmware backup on hand · Windows sleep disabled.

**Phase 1 done when**
- [ ] Simulation: full sample print completes with one operator-confirmed insert.
- [ ] Hardware: same, on the printer, on a real coupon from Phase 0.
- [ ] All 1.x tasks' success criteria met; tests cover happy path + ack timeout + missing sentinel.

---

### Phase 2 — Actuated placer MCU

**Goal.** Replace the operator's hand with a mechanism: the host tells a
microcontroller to place one magnet, and the insert sequence calls it instead of
prompting.

| # | Task | Files affected | Success criteria |
|---|------|----------------|------------------|
| 2.1 | Choose MCU + placer kinematics | `project/PROJECT_PLAN.md` §7, `placer_fw/README.md` | MCU (ESP32 vs Pico), actuator type (servo arm / solenoid + gravity magazine), and mounting decided and written down |
| 2.2 | MCU firmware | `placer_fw/` (Arduino/PlatformIO sketch) | Responds to `PING`→`PONG`, `PLACE`→`DONE`/`ERR <reason>` over USB serial; single place cycle is repeatable by hand test |
| 2.3 | `PlacerLink` + `placer_sim` | `magnet_embed/links/placer_link.py`, `magnet_embed/links/placer_sim.py` | `place()` returns on `DONE`, raises `PlacerError` on `ERR`; sim mirrors both; unit-tested |
| 2.4 | `placer_serial` | `magnet_embed/links/placer_serial.py` | `--ping` returns `PONG` against the real MCU |
| 2.5 | Wire into the sequence | `magnet_embed/sequences/insert_magnet.py`, `magnet_embed/main.py` | When a placer is present, `insert_magnet` calls `placer.place()`; operator `confirm()` becomes the fallback |
| 2.6 | End-to-end hardware run | — | Print → automatic place → resume → sealed part, unattended through the insert |

**Phase 2 done when**
- [ ] 5 consecutive coupons printed with automatic magnet placement, 0 misplacements.
- [ ] A placer `ERR` mid-print leaves the printer paused and resumable, not crashed.

---

### Phase 3 — Hardening (later)

**Goal.** Make it tolerant of the things that go wrong on a real bench.

- [ ] Nozzle wipe + temp-drop tuning to kill ooze strings during the pause
- [ ] Failure recovery: placer jam, magnet missing from magazine, serial disconnect mid-pause
- [ ] Multi-magnet parts: multiple sentinels, per-sentinel park points
- [ ] Config UI in the panel instead of hand-editing YAML
- [ ] Run log / print report written to `logs/`

---

## 5. Consolidated To-Do Checklist

### Phase 0 — Mechanical proof
- [ ] Model test coupon with magnet pocket
- [ ] Slice with slicer pause-at-layer
- [ ] Print + manual insert + resume
- [ ] Verify cap bonding, magnet capture, pull strength
- [ ] Record magnet grade / dimensions / pocket clearance in §7

### Phase 1 — Python host + Tkinter
- [ ] 1.1 Repo scaffold (`magnet_embed/`, venv, `requirements.txt`, `config.yaml`)
- [ ] 1.2 `PrinterState` + `PrinterLink` abstract
- [ ] 1.3 `printer_sim`
- [ ] 1.4 `GcodeRunner` (stream + ok + pause/resume/cancel + sentinel)
- [ ] 1.5 `gcode/postprocess.py` + CLI
- [ ] 1.6 `sequences/insert_magnet.py` (operator confirm)
- [ ] 1.7 `ui/panel.py` + `main_sim.py`
- [ ] 1.8 `printer_serial` + `main.py` + hardware smoke test
- [ ] Tests: runner, postprocess, insert sequence, printer sim
- [ ] Pre-hardware gate passed
- [ ] Full sim print completes with operator insert
- [ ] Full hardware print completes with operator insert

### Phase 2 — Actuated placer MCU
- [ ] 2.1 Choose MCU + placer kinematics
- [ ] 2.2 MCU firmware (`PING` / `PLACE`)
- [ ] 2.3 `PlacerLink` + `placer_sim`
- [ ] 2.4 `placer_serial` + `--ping` on real MCU
- [ ] 2.5 Wire `place()` into `insert_magnet`
- [ ] 2.6 End-to-end automatic-place hardware run
- [ ] 5 consecutive clean coupons
- [ ] Placer `ERR` leaves printer resumable

### Phase 3 — Hardening
- [ ] Nozzle wipe / temp-drop tuning
- [ ] Failure recovery (jam, missing magnet, disconnect)
- [ ] Multi-magnet parts
- [ ] In-panel config
- [ ] Run log / print report to `logs/`

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| USB tether drops mid-print | Print aborts | Disable Windows sleep; short cable; `GcodeRunner` pauses (not aborts) on serial error and lets the operator reconnect |
| Long pause → nozzle ooze / part shift | Failed layer on resume | Keep pause short; drop nozzle temp during pause; wipe before resume (Dev Rule 6) |
| Insertion force knocks the part → layer shift | Ruined print | Head parks clear before insert; placer must not push on the part (Dev Rule 7) |
| Magnet demagnetised by nozzle heat | Weak part | Phase 0 measures this; move to N42SH/UH grade if needed |
| Creality serial quirks (`ok` handling, no temp autoreport) | Host stalls | Use `printrun.printcore` which handles these; `wait_ok` has a timeout + `AckTimeout` |
| Klipper/OctoPrint temptation creeps scope | Delays prototype | Explicitly out of scope §1; revisit only after Phase 2 |
| Placer MCU adds a 2nd failure domain | Print pauses on MCU fault | `PLACE`→`ERR` path keeps the printer paused + resumable; operator fallback stays wired |

---

## 7. Open Questions & Findings

Fill in as Phase 0 progresses.

- Magnet: grade? diameter × thickness? ______
- Pocket clearance that gives a reliable drop-in without rattle: ______
- Cap layer count for full seal: ______
- Does nozzle temp during pause need lowering, and to what: ______
- Phase 2 MCU: ESP32 or Pico? ______
- Phase 2 actuator: servo arm, solenoid + gravity magazine, or other? ______
