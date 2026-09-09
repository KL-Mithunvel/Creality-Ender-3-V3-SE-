# TODO

Phased plan for the Ender-3 V3 SE magnet-embedding print assistant.
**Authoritative plan: `project/PROJECT_PLAN.md`** (goals, steps, files, success
criteria, risks). Architecture and rules: `.CLAUDE/CLAUDE.md`. Keep all three in sync.

## In Progress


## Done

- [x] Scope printer-control options and pick a direction — Python host script (`pyserial` /
      `printrun.printcore`) + Tkinter panel; actuated placer on a separate ESP32/Pico MCU
      (Phase 2); PC tethered over USB-C, no Raspberry Pi.
- [x] Fill in `.CLAUDE/CLAUDE.md` with the real project brief; populate this file and README.
- [x] Write `project/PROJECT_PLAN.md` (multi-phase plan + consolidated checklist); add `.gitignore`.

## Not Started

### Phase 0 — mechanical proof (no host code)
- [ ] Design a test part with a magnet pocket (top layers form the seal cap)
- [ ] Slice with slicer pause-at-layer (`M0`), insert magnet by hand, verify encapsulation and magnet strength
- [ ] Decide magnet grade and polarity-marking procedure

### Phase 1 — Python host + Tkinter, operator-triggered place
- [ ] Repo scaffold: `magnet_embed/` package, venv, `requirements.txt`, `config.yaml`
- [ ] `PrinterLink` abstract + `printer_sim`
- [ ] `GcodeRunner`: stream + `ok` handshake + pause/resume/cancel + sentinel detection
- [ ] `gcode/postprocess.py`: sentinel injection (Cura + PrusaSlicer markers) + CLI
- [ ] `sequences/insert_magnet.py` with an operator-confirm callback
- [ ] `ui/panel.py` Tkinter control panel
- [ ] Tests: runner, postprocess, insert sequence, printer sim
- [ ] `printer_serial` real link + hardware smoke test on the V3 SE

### Phase 2 — actuated placer MCU
- [ ] Choose MCU (ESP32 vs Pico) and placer kinematics (servo arm / solenoid + magazine)
- [ ] MCU firmware: `PING` / `PLACE` serial protocol
- [ ] `PlacerLink` abstract + `placer_sim` + `placer_serial`
- [ ] Wire `insert_magnet` to call `placer.place()` instead of the operator prompt
- [ ] End-to-end hardware run: print -> auto-place -> encapsulate

### Phase 3 — hardening (later)
- [ ] Nozzle wipe / temp-drop tuning
- [ ] Failure recovery (placer jam, magnet missing, mid-pause disconnect)
- [ ] Multi-magnet parts
