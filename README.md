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

1. Slice the part in Creality Print (magnet pocket a few layers below the top
   surface, press-fit) and bring the finished `.gcode`.
2. In the app: load the file, **see the toolpath and the simulated insert motion**
   (`--preview`), then **Plan magnet insert…** — set the pocket X/Y, seat height and
   shear direction, envelope-check it, and **Save `*.magnet.gcode`** (a
   `;MAGNET_INSERT X Y Z S<dir>` comment; the file still prints from microSD).
   The CLI `magnet_embed.gcode.postprocess` does the same headlessly.
3. The host streams the G-code; on the sentinel it saves position, parks, dispenses a
   magnet (operator-triggered in Phase 1, Arduino in Phase 2), moves the holding pole
   over the pocket using the tool offset, presses the magnet in (Z), shears the pole
   away (lateral), asks the operator Success / Retry / Abort, then returns to the saved
   position and resumes so the remaining layers seal over the magnet. No homing mid-print.

## Quick start

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

python main.py                          :: simulator + GUI — safe on any machine
python main.py --printer part.gcode     :: real printer over USB, no dispenser
python main.py --hardware               :: real printer + Arduino dispenser
python main.py --hardware --ping        :: connect to both, report, exit
python main.py --sim --no-gui part.gcode --confirm success   :: headless run
```

One entry point, mode chosen by flag: `--sim` (default) / `--printer` / `--hardware`.
The `python -m magnet_embed.main*` modules still work (thin wrappers) for
back-compat. Run the pre-hardware checklist in `.CLAUDE/CLAUDE.md` before
`--printer` / `--hardware`.

## Documents

| File | What |
|------|------|
| `.CLAUDE/CLAUDE.md` | Full project brief — architecture, modules, conventions, rules |
| `project/HOW_IT_WORKS.md` | Plain-language walkthrough of the whole system (start here if new) |
| `project/PROJECT_PLAN.md` | Multi-phase plan — goals, steps, files, success criteria, risks, checklist |
| `project/BUILD_PLAN.md` | Software build broken into commit-sized chunks (C1–C8, Phase 1.6 C13–C19) + protocol notes |
| `project/RESEARCH.md` | Prior art & similar projects survey (OctoPNP, in-situ-placement papers, host-control patterns) + how each informs the design |
| `docs/INVENTION_DISCLOSURE_DRAFT.md` | Working draft of the patent disclosure form (for inventor + attorney review) |
| `TODO.md` | Task tracker (mirrors the plan checklists) |
| `.CLAUDE/CLAUDE-LOG.md` | Session-by-session history |

## Status

**Phase 1 + Phase 1.6 software complete (170 tests).** One `python main.py`
(mode by flag) drives the whole workflow against a simulated printer + dispenser:
import a slice → visualise the toolpath → simulate the magnet-insert motion →
place the sentinel and save `*.magnet.gcode` → stream it → park / dispense / press /
shear / Success·Retry·Abort / resume. The panel has jog/home, raw G-code, temps,
extrude/retract, idle polling and a run-progress bar. The **printer serial link is
verified on real hardware** (COM3).

Next for the magnet flow: build the clip-on applicator + Arduino sketch, measure
the tool offset, run the manual hardware smoke test. See `project/BUILD_PLAN.md`
and `project/PROJECT_PLAN.md`.
