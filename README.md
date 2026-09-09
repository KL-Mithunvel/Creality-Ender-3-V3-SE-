# Creality Ender-3 V3 SE — Magnet-Embedding Print Assistant

A semi-automated workflow that lets the printer **print a part, pause at a known
layer, embed a permanent magnet into a printed pocket, then resume and seal the
part over the magnet**. Prototype-stage; manual operator involvement is expected.

## Setup

| Piece | Choice |
|-------|--------|
| Printer | Creality Ender-3 V3 SE — Marlin firmware, USB-C serial @ 115200, no networking |
| Host | Windows 11 PC, Python + Tkinter, tethered over USB-C for the whole print |
| Magnet placer | Separate ESP32 / RP2040 (Pico) microcontroller on a second USB serial port (Phase 2) |
| Control | Python host script (`pyserial` / `printrun.printcore`) — no firmware reflash |

## How it works

1. Slice the part (magnet pocket a few layers below the top surface).
2. `magnet_embed.gcode.postprocess` injects a `;MAGNET_INSERT` comment at the target layer.
3. The host streams the G-code to the printer; on the sentinel it parks the head,
   places the magnet (operator-triggered in Phase 1, MCU-actuated in Phase 2),
   then resumes so the remaining layers seal over the magnet.

## Quick start (once code exists)

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python magnet_embed\main_sim.py     :: simulation — no hardware
python magnet_embed\main.py         :: hardware — after the pre-hardware checklist
```

## Documents

| File | What |
|------|------|
| `.CLAUDE/CLAUDE.md` | Full project brief — architecture, modules, conventions, rules |
| `project/PROJECT_PLAN.md` | Multi-phase plan — goals, steps, files, success criteria, risks, checklist |
| `TODO.md` | Task tracker (mirrors the plan checklist) |
| `.CLAUDE/CLAUDE-LOG.md` | Session-by-session history |

## Status

Planning / scaffolding — no code yet. Next up: Phase 0 (mechanical proof) in
`project/PROJECT_PLAN.md`.
