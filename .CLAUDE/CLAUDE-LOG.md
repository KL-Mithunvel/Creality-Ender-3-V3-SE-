# Claude Log

## 2026-09-09 — Project scoping: printer-control options + doc scaffolding

- Reviewed the repo — it was the untouched shared `CLAUDE.md` template library
  (`CLAUDE.md`, `CLAUDE-COMMON.md`, `PROJ_STARTER.md`), no project content.
- Analysed ways to control a Creality Ender-3 V3 SE for a magnet-embedding
  prototype (print a part, pause, embed a magnet in a printed pocket, resume):
  slicer pause-at-layer, Pronterface/Printrun, Python host script over serial,
  OctoPrint on a Pi, Klipper + Moonraker. Compared on manual-vs-automated,
  extra hardware, scriptability, risk to the printer, effort.
- Key V3 SE facts confirmed for the brief: Marlin-based, USB-C serial at 115200,
  microSD, **no networking**, standard pause primitives (`M0`/`M25`/`M600`).
- Owner decisions:
  - Control: **Python host script** (`pyserial` / `printrun.printcore`) + **Tkinter** panel.
  - Magnet placement: **actuated placer on a separate ESP32/Pico MCU** (Phase 2);
    operator-triggered in Phase 1.
  - Topology: **PC tethered to the printer over USB-C**; no Raspberry Pi.
- Rewrote `.CLAUDE/CLAUDE.md` as a real project brief: Project Overview, Running
  the System, Architecture (module table, data-flow diagram, threading model),
  Key Modules (intended interfaces), Key Conventions (the `;MAGNET_INSERT`
  sentinel, layer targeting, placer serial protocol), Data Files, Platform
  Constraints, Deployment Notes (Windows dev == runtime; hardware last),
  Known Technical Debt (none), 10 numbered Development Rules, phased TODO list,
  User Rules. Deleted the Schema Reference section (no data layer).
- Populated root `TODO.md` with the phased plan; wrote `README.md`.
- `CLAUDE-COMMON.md` left untouched (shared file).
- No code written yet — `magnet_embed/` package does not exist.

## 2026-09-09 — Project plan document + first commit

- Wrote `project/PROJECT_PLAN.md` — the authoritative multi-phase plan: objective
  and scope, locked decisions, architecture summary, Phase 0–3 with per-task files
  affected and success criteria, a consolidated checkbox to-do list, a risks table,
  and an open-questions section for Phase 0 findings.
- Added `.gitignore` (`.idea/`, `venv/`, `__pycache__/`, generated `*.gcode`,
  `logs/`, `config.local.yaml`).
- Cross-linked the plan from `.CLAUDE/CLAUDE.md` (TODO section + Data Files),
  `TODO.md`, and `README.md`; `TODO.md` now mirrors the plan checklist.
- Committed everything to `main` (was still just the template + the earlier
  uncommitted doc rewrite). `.idea/` excluded via `.gitignore`. (27ebf21)

## 2026-09-09 — Mechanism design nailed down; docs updated to match

- Worked through the physical sequence with the owner. Corrections from the earlier
  assumptions:
  - Dispenser MCU is an **Arduino Uno** (not ESP32/Pico). Renamed `placer*` →
    `dispenser*` throughout the docs.
  - The **servo only dispenses** one magnet from a magazine onto a holding pole.
  - **Press and shear are printer moves**, not servo moves — Z press to seat depth,
    then a short **lateral** shear so the pole slides off (vertical shear would pull
    the magnet back out). Shear direction carried in the sentinel.
  - **No `G28` mid-print** — save state, restore exact coordinates. Added Dev Rules
    11 (no homing), 12 (in-envelope check), 13 (Uno stays dumb).
  - Magnet **polarity is deterministic** via the holding pole — no per-magnet marking.
  - Assumption recorded: the applicator is a **clip-on** add-on and for now is assumed
    not to hinder normal printing (no tool-lift servo, no nozzle Z-clearance handling).
- Extended the sentinel to `;MAGNET_INSERT X<px> Y<py> Z<seat_z> S<dir>` and wrote the
  full `SAVE → PARK → DISPENSE → APPROACH → PRESS → SHEAR → LIFT → ASK → RESUME` state
  machine into `.CLAUDE/CLAUDE.md` (Architecture) and `project/PROJECT_PLAN.md` (Phase 2).
- Rewrote `project/PROJECT_PLAN.md`: §2 assumptions, §3 mechanism + decisions +
  Uno protocol, §4 state machine, §5 Phase 1/2 task tables, §6 tool-offset/reachable
  area, §7 risks, §8 open questions.
- Updated `.CLAUDE/CLAUDE.md` (overview, module table, data flow, insert-sequence
  subsection, Key Modules, Key Conventions, Platform Constraints, Deployment Notes,
  Dev Rules, Phase 2 TODO, overrides), `TODO.md`, and `README.md` to match.
- Still no code — `magnet_embed/` does not exist yet. (cf194a9)

## 2026-09-09 — Software build plan + research

- Researched host-controlled G-code streaming: Printrun `printcore.py` (`clear`-flag
  ack loop, resend, pause/resume), OctoPrint `comm.py` / serial schema / virtual
  printer (firmware-quirk handling, sim model), Marlin g-code docs (M400 gates real
  motion completion — `ok` only means "buffered"; M115/M114/M155/M109), minimal
  senders (PyGcodeSender, gcode-cli), Ender 3 V3 SE OctoPrint friction (M110, host
  action commands — plain-line streaming avoids it), Arduino auto-reset
  (`dtr=False` before open), and component-embedding-via-pause prior art.
- Wrote `project/BUILD_PLAN.md`: protocol notes (receive-line handling table,
  connect settle, M-code cheatsheet), chunks C1–C6 (files + tests + acceptance,
  one commit each), and a References section with all the links.
- Cross-linked BUILD_PLAN from `CLAUDE.md`, `PROJECT_PLAN.md`, `TODO.md`, `README.md`;
  `TODO.md` Phase 1 now tracks C1–C6.
- Decisions baked into the plan: plain-line streaming (no `M110`/checksums unless the
  printer requests resends); `M400` gates every insert-sequence phase; `SimPrinter`
  models the OctoPrint virtual-printer idea; hardware smoke test stays a manual step.
- Next: execute C1.

