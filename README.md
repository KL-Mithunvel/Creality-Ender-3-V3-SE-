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

## Testing & sanity checks

Everything below assumes `.venv` is active (`.venv\Scripts\activate`).

**Automated tests — no hardware needed:**

```bat
python -m pytest                          :: full suite (248 tests)
python -m py_compile main.py magnet_embed\*.py magnet_embed\ui\*.py magnet_embed\gcode\*.py magnet_embed\sequences\*.py magnet_embed\links\*.py magnet_embed\viz\*.py
```

**Serial sanity tests — need the real hardware plugged in:**

```bat
python main.py --printer --ping                          :: printer only, no GUI
python main.py --hardware --ping                         :: printer + Arduino Uno (Phase 2)
python -m magnet_embed.links.printer_serial --ping       :: printer link in isolation (M115/M400/M114)
python -m magnet_embed.links.dispenser_serial --ping      :: Uno link in isolation (-> PONG); Phase 2, not built yet
```

**Running `main.py` with a G-code file loaded:**

```bat
python main.py                                                          :: GUI, no file — load one from the panel
python main.py --sim tests\data\sample.gcode --no-gui --confirm success :: headless sim run, auto-confirms the insert prompt
python main.py --printer part.gcode                                     :: real printer, GUI opens with the file pre-loaded
python main.py --hardware part.magnet.gcode                             :: real printer + Uno, GUI pre-loaded
python main.py --preview part.magnet.gcode                              :: toolpath + insert-motion preview, then exits (no streaming)
```

**Preparing a `*.magnet.gcode` for a test run** (or use the panel's **Plan magnet
insert…** dialog, which does the same and auto-loads the result):

```bat
python -m magnet_embed.gcode.postprocess part.gcode --layer 40 --xy 120.5 98 --seat-z 6.2 --shear +X -o part.magnet.gcode
```

Run the "Pre-hardware checklist" in `.CLAUDE/CLAUDE.md` → Deployment Notes before
the first `--printer` / `--hardware` run on a given machine.

## Documents

| File | What |
|------|------|
| `.CLAUDE/CLAUDE.md` | Full project brief — architecture, modules, conventions, rules |
| `project/HOW_IT_WORKS.md` | Plain-language walkthrough of the whole system (start here if new) |
| `project/PROJECT_PLAN.md` | Multi-phase plan — goals, steps, files, success criteria, risks, checklist |
| `project/BUILD_PLAN.md` | Software build broken into commit-sized chunks (C1–C8, Phase 1.6 C13–C19, Phase 1.7 C20, Phase 1.8 C21, Phase 1.9 C22, Phase 1.10 C23, Phase 1.11 C24, Phase 1.12 C25, Phase 1.13 C26) + protocol notes |
| `project/RESEARCH.md` | Prior art & similar projects survey (OctoPNP, in-situ-placement papers, host-control patterns) + how each informs the design |
| `docs/INVENTION_DISCLOSURE_DRAFT.md` | Working draft of the patent disclosure form (for inventor + attorney review) |
| `TODO.md` | Task tracker (mirrors the plan checklists) |
| `.CLAUDE/CLAUDE-LOG.md` | Session-by-session history |

## Status

**Phase 1 + Phase 1.6 through Phase 1.13 software complete (248 tests).**
The magnet insert is guarded against damage (C25): the Plan dialog, the
preview and the run itself refuse — with the reason — a pocket off the bed, a
press into the build plate, or a press/shear that would drive the nozzle into
the printed part, and a red **EMERGENCY STOP** (`M112`) is always one click
away. The live-print view tracks the actual insert-motion waypoints (C26)
instead of freezing while a magnet insert runs. One `python main.py` (mode by
flag) opens **maximized** and drives the whole workflow against a simulated
printer + dispenser: import a slice → visualise the toolpath → simulate the
magnet-insert motion → place the sentinel and save `*.magnet.gcode` → stream
it → park / dispense / press / shear / Success·Retry·Abort / resume. The
panel is a two-column layout (jog/temperature/filament on the left; the live
view, send-G-code, and log on the right, stretching to fill the window) and
scrollable as a fallback on a smaller screen; it shows what it's actually
connected to (`"simulator"` / `"printer COM3"`), and has jog/home, raw
G-code, extrude/retract, idle polling, a run-progress bar, and an embedded
**live-print view** showing the current layer in 2D and an isometric 3D view
**side by side** — the 3D view has a **"Global bed" / "Local part"** toggle
(the whole bed for scale/context, or a tight crop around just the part so a
short/flat print is actually visible), true equal-mm-per-axis proportions
with tight axis limits (no more odd Z-axis gaps), and a path that grows as
the nozzle actually passes through it, redrawn ~6–7×/s for smooth motion —
plus a nozzle-position marker and the current G-code step's text under both.
A guided **"Z Calibrate…"** paper-test Z-offset dialog rounds it out (config
is the trusted offset, `M851`+`M500` on save — **not yet bench-tested on
real hardware**). "Plan magnet insert…" now shows an embedded live preview
of the planned insert motion as you edit the pocket coordinates. Nozzle/bed
**temperature can be changed even during a print** (locked against the
streaming loop, blocked only while the magnet-insert sequence owns the
heaters), with the allowed range and a live current-temp readout shown next
to each entry. The **printer serial link is verified on real hardware**
(COM3).

Next for the magnet flow: build the clip-on applicator + Arduino sketch, measure
the tool offset, run the manual hardware smoke test — and bench-test the new
Z-calibration workflow before trusting it. See `project/BUILD_PLAN.md` and
`project/PROJECT_PLAN.md`.
