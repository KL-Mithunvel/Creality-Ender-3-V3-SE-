# Creality Ender-3 V3 SE — Magnet-Embedding Print Assistant

A semi-automated workflow that lets the printer **print a part, pause at a known
layer, embed a permanent magnet into a printed pocket, then resume and seal the
part over the magnet**. Prototype-stage; manual operator involvement is expected.

## Setup

| Piece | Choice |
|-------|--------|
| Printer | Creality Ender-3 V3 SE — Marlin firmware, USB-C serial @ 115200, no networking |
| Host | Windows 11 PC, Python + Tkinter, tethered over USB-C for the whole print |
| Applicator | Clip-on toolhead add-on; an **Arduino Uno** drives one servo that dispenses a magnet to a holding pole (Phase 2) |
| Press + shear | Done by the **printer's own motion** — Z press, lateral shear — not the servo |
| Control | Python host script (`pyserial` / `printrun.printcore`) — no firmware reflash |

## How it works

1. Slice the part (magnet pocket a few layers below the top surface, press-fit).
2. `magnet_embed.gcode.postprocess` injects a `;MAGNET_INSERT X Y Z S<dir>` comment
   at the target layer (pocket location + seat height + shear direction).
3. The host streams the G-code; on the sentinel it saves position, parks, dispenses a
   magnet (operator-triggered in Phase 1, Arduino in Phase 2), moves the holding pole
   over the pocket using the tool offset, presses the magnet in (Z), shears the pole
   away (lateral), asks the operator Success / Retry / Abort, then returns to the saved
   position and resumes so the remaining layers seal over the magnet. No homing mid-print.

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
| `project/HOW_IT_WORKS.md` | Plain-language walkthrough of the whole system (start here if new) |
| `project/PROJECT_PLAN.md` | Multi-phase plan — goals, steps, files, success criteria, risks, checklist |
| `project/BUILD_PLAN.md` | Software build broken into commit-sized chunks (C1–C6) + protocol notes + references |
| `docs/INVENTION_DISCLOSURE_DRAFT.md` | Working draft of the patent disclosure form (for inventor + attorney review) |
| `TODO.md` | Task tracker (mirrors the plan checklists) |
| `.CLAUDE/CLAUDE-LOG.md` | Session-by-session history |

## Status

**Phase 1 software complete** — the full control stack (streaming, sentinel
detection, the park→dispense→press→shear→resume insert sequence, post-processor,
Tkinter panel, real serial links) works against a simulated printer + dispenser,
with 94 passing tests. It has **not** run on real hardware yet.

Next: build the clip-on applicator + Arduino sketch, measure the tool offset, and
run the manual hardware smoke test. See `project/BUILD_PLAN.md` and
`project/PROJECT_PLAN.md`.
