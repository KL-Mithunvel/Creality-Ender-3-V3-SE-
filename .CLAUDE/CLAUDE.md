# CLAUDE.md

> **IMPORTANT:** Read `.CLAUDE/CLAUDE-COMMON.md` first — general must-follow instructions
> (companion files, deployment model, workflow, documentation discipline). This file
> holds repo-specific instructions and **overrides** `CLAUDE-COMMON.md` where they conflict.
>
> **Also read `.CLAUDE/PROJ_STARTER.md`** — the owner's personal interaction rules,
> coding standards, tech-stack defaults, and commit style. They apply to every session here.
>
> This repo started from the shared `CLAUDE.md` template library. It is now a real
> project brief, not a template — the "how to start a new project" scaffolding has been
> replaced with project content.

---

## Project Overview

**Creality Ender-3 V3 SE — Magnet-Embedding Print Assistant.**

A semi-automated workflow that lets the printer **print a part, pause at a known
layer, embed a permanent magnet into a printed pocket, then resume and seal the
part over the magnet**. Built by kl mithunvel as a prototype; manual operator
involvement is acceptable at this stage.

- **Printer:** Creality Ender-3 V3 SE — Marlin-based firmware, standard G-code.
  USB-C serial control channel at **115200 baud**. microSD for standalone prints.
  **No Wi-Fi / Ethernet** on the SE. CR-Touch ABL, dual-Z, Sprite direct-drive
  extruder, ~250 mm/s ceiling.
- **Host:** the owner's **Windows 11** PC, tethered to the printer over USB-C for
  the whole print. Python + Tkinter control panel. No Raspberry Pi in the loop.
- **Magnet placer:** a **separate microcontroller** (ESP32 or RP2040 / Pico) that
  drives the physical placer actuator. The host talks to it over a second USB
  serial port. Actuation lands in Phase 2; Phase 1 is operator-triggered.
- **License:** see `LICENSE`. **Entry points:** `magnet_embed/main_sim.py`
  (simulation) and `magnet_embed/main.py` (hardware). **Min runtime:** Python 3.12.

### Chosen control approach (and the options considered)

| Option | Verdict |
|--------|---------|
| Slicer pause-at-layer only (`M0`), manual insert | **Phase 0** — used to prove the mechanical/encapsulation concept only. No code. |
| Pronterface / Printrun GUI | Bring-up / manual console only, not the product. |
| **Python host script (`pyserial` / `printrun.printcore`) + Tkinter panel** | **Chosen.** Matches the owner's stack, no firmware reflash, runs from the Windows PC. |
| OctoPrint on a Raspberry Pi | Rejected for now — adds a device; no Pi wanted. |
| Klipper + Moonraker | Rejected for now — requires reflashing the printer and losing the stock screen. Revisit only if macro unification becomes compelling. |

---

## Running the System

> Code does not exist yet — this section is the intended shape. Activate the venv first, always.

```bat
:: one-time setup (Windows)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt        :: uv migration planned — prefer uv when it lands

:: simulation — no hardware, safe on any machine
python magnet_embed\main_sim.py

:: tests + lint (run before every commit)
python -m pytest
python -m py_compile magnet_embed\*.py

:: G-code prep: inject the magnet sentinel at a layer / height
python -m magnet_embed.gcode.postprocess part.gcode --layer 40 -o part.magnet.gcode

:: hardware run — only after the pre-hardware checklist passes
python magnet_embed\main.py
```

Simulation vs hardware is selected **by entry point**, not by a flag in code:
`main_sim.py` wires the simulated links, `main.py` wires the serial links. Both read
the same `magnet_embed/config.yaml`.

---

## Architecture

### Module responsibilities

| Path | Role |
|------|------|
| `magnet_embed/config.yaml` | All ports, baud rates, park coordinates, safe-Z, temps, sentinel token. Nothing hardware-specific is hardcoded elsewhere. |
| `magnet_embed/main.py` | Hardware entry point — real printer + real placer MCU. |
| `magnet_embed/main_sim.py` | Dev entry point — simulated printer + simulated placer. |
| `magnet_embed/state.py` | `PrinterState` dataclass (position, temps, connection, run status). |
| `magnet_embed/links/printer_link.py` | Abstract `PrinterLink` — `connect`, `send_line`, `wait_ok`, `disconnect`. |
| `magnet_embed/links/printer_serial.py` | Real printer link — `pyserial` / `printrun.printcore`, 115200, `ok`-handshake, temp parsing. |
| `magnet_embed/links/printer_sim.py` | Simulated printer — consumes G-code, tracks X/Y/Z/E and temps, emits `ok`, raises the same exceptions as the real link. |
| `magnet_embed/links/placer_link.py` | Abstract `PlacerLink` — `ping`, `place`, error reporting. |
| `magnet_embed/links/placer_serial.py` | Real placer link — serial to the ESP32/Pico, ASCII line protocol. |
| `magnet_embed/links/placer_sim.py` | Simulated placer — returns `DONE` / `ERR` like the real MCU. |
| `magnet_embed/gcode/runner.py` | `GcodeRunner` — streams lines, waits for `ok`, detects the sentinel, handles pause / resume / cancel. |
| `magnet_embed/gcode/postprocess.py` | Inserts the sentinel comment line at a chosen layer index or Z height. |
| `magnet_embed/sequences/insert_magnet.py` | The park → lift → (optional temp drop) → place → wipe → resume routine. |
| `magnet_embed/ui/panel.py` | Tkinter panel — connect, home, jog, load G-code, run, pause/resume, "Insert Magnet", live log. |
| `tests/` | `pytest` — runner, postprocess, insert sequence, printer sim. |

### Data flow

```
Creality Print / Cura ──slice──► part.gcode
                                     │
              gcode/postprocess.py inserts  ";MAGNET_INSERT"  at layer N
                                     │
                                     ▼
   ┌──────────────── host: Windows 11 PC (Python) ─────────────────┐
   │  ui/panel.py ──► gcode/runner.py ──► links/printer_serial ────┼──USB-C serial 115200──►  Ender-3 V3 SE
   │                        │                                      │
   │       on ";MAGNET_INSERT":                                    │
   │                        └──► sequences/insert_magnet ──────────┤
   │                                    │                          │
   │                                    └──► links/placer_serial ──┼──USB serial──►  Placer MCU (ESP32 / Pico)   [Phase 2]
   └──────────────────────────────────────────────────────────────┘
```

### Threading model

- Tkinter main loop on the main thread.
- G-code streaming on one worker thread (`GcodeRunner.run()`).
- Each serial link has its own reader thread.
- Threads talk to the UI through a thread-safe queue polled via `root.after(...)`.
  No Tkinter calls off the main thread.

### Simulation vs real

Chosen by entry point. `printer_sim` / `placer_sim` produce the same return
shapes and raise the same exception types as the serial links, so `GcodeRunner`,
`insert_magnet`, and the UI are exercised end-to-end on the dev machine with no
hardware attached.

---

## Key Modules

> Interfaces are the intended contract; implementations do not exist yet.

### `links/printer_link.py` — `PrinterLink` (abstract)
- `connect() -> None` — open the port, wait for the firmware banner. Raises `PrinterConnectionError`.
- `send_line(line: str) -> None` — write one G-code line (no newline needed).
- `wait_ok(timeout_s: float) -> str` — block until `ok`; return any payload (temps). Raises `AckTimeout`.
- `query_state() -> PrinterState`.
- `disconnect() -> None`.
- I/O: serial port from `config.yaml`.

### `links/placer_link.py` — `PlacerLink` (abstract)
- `ping() -> bool` — `PING` → `PONG`.
- `place() -> None` — run one place cycle. Raises `PlacerError` on `ERR <reason>`.
- I/O: second serial port from `config.yaml`.

### `gcode/runner.py` — `GcodeRunner`
- `__init__(link: PrinterLink, gcode_path: str, on_sentinel: Callable, config: dict)`.
- `run() -> None` — stream every line, `wait_ok` after each; when a stripped line equals the
  sentinel token, call `on_sentinel()` instead of sending it, then continue.
- `pause()`, `resume()`, `cancel()` — thread-safe.
- Side effects: reads the G-code file, writes to the printer link, appends to the run log.
- Exceptions: `AckTimeout`, `SentinelNotFound` (if `require_sentinel` and EOF reached first).

### `gcode/postprocess.py`
- `inject_sentinel(in_path, out_path, *, layer: int | None, z_mm: float | None) -> int`
  — returns the source line number where the sentinel was inserted.
- Understands Cura / Creality Print (`;LAYER:<n>`) and PrusaSlicer (`;LAYER_CHANGE` + `;Z:<h>`) markers.
- CLI: `python -m magnet_embed.gcode.postprocess <file> --layer N | --z H [-o OUT]`.

### `sequences/insert_magnet.py`
- `insert_magnet(printer: PrinterLink, placer: PlacerLink | None, config: dict, confirm: Callable[[], bool]) -> None`
- Steps: record current XYZ/temp → move to `park_xy` at `safe_z_lift_mm` above the part →
  optionally set nozzle to `pause_nozzle_temp_c` → `placer.place()` **or** `confirm()` (Phase 1) →
  optional nozzle wipe → restore temp → return head to the saved position → hand control back to the runner.
- **Must** leave the printer resumable on any failure: restore temp, no partial moves, re-raise. Never swallow.

### `ui/panel.py`
- `ControlPanel(root, printer, placer, config)` — buttons/fields for connect, home (`G28`),
  jog (±X/Y/Z step), set temps, load G-code, run, pause/resume/cancel, "Insert Magnet" (manual trigger),
  and a scrolling serial log.

---

## Key Conventions

- **Magnet sentinel — `;MAGNET_INSERT`.** A bare G-code **comment** line inserted by
  `gcode/postprocess.py` at the chosen layer. Because it is a comment, the file still
  prints normally straight from microSD. `GcodeRunner` compares each line **after
  `.strip()`** against `config['gcode']['sentinel_token']` (default `;MAGNET_INSERT`);
  on a match it fires the insert sequence and does **not** send the line to the printer.
- **Layer / height targeting.** `postprocess.inject_sentinel` finds the insertion point
  from slicer layer markers: `;LAYER:<n>` (Cura / Creality Print) or `;LAYER_CHANGE`
  followed by `;Z:<height>` (PrusaSlicer). `--layer` matches the marker index; `--z`
  matches the first layer whose height ≥ the value.
- **Placer MCU protocol** — newline-terminated ASCII over serial, deliberately dumb:
  - host → MCU: `PING\n`, `PLACE\n`
  - MCU → host: `PONG\n`, `DONE\n`, or `ERR <reason>\n`
- **Config precedence.** Everything hardware-specific (COM ports, baud, `park_xy`,
  `safe_z_lift_mm`, `pause_nozzle_temp_c`, `sentinel_token`) lives in
  `magnet_embed/config.yaml` and is passed as parameters. Simulated links ignore the
  port keys. There are **no** hardcoded ports, coordinates, or temps in link or
  sequence files.
- **Magnet handling (operator procedure, not code).** Mark polarity before insertion.
  Keep the pause short — nozzle ooze and part shift grow with pause time. If magnets
  weaken across prints, move from N-grade to a high-temp grade (N42SH/UH).

---

## Data Files

| File | Tracked? | Notes |
|------|----------|-------|
| `.CLAUDE/*.md`, `project/PROJECT_PLAN.md`, `README.md`, `TODO.md` | yes | Project docs. `CLAUDE-COMMON.md` is shared — never edit here. |
| `.gitignore` | yes | Excludes `.idea/`, `venv/`, `__pycache__/`, generated G-code, `logs/`, `config.local.yaml`. |
| `magnet_embed/config.yaml` | yes | Committed with safe defaults; local COM ports may be overridden — see below. |
| `*.gcode`, `*.magnet.gcode` | **no** — gitignore | Sliced parts and post-processed output. Generated, not committed. |
| `logs/*.log` | **no** — gitignore | Per-run serial transcripts. |
| `requirements.txt` | yes | Pinned deps (`pip freeze` after installs). |
| MCU firmware source (`placer_fw/`) | yes | Phase 2 — ESP32/Pico sketch. |

If a local machine needs different COM ports than the committed `config.yaml`, use a
gitignored `config.local.yaml` (loaded over `config.yaml` when present) rather than
editing the tracked file.

---

## Platform Constraints

- **Host OS:** Windows 11 (the owner's machine). Code should also run on Linux / Raspberry Pi OS —
  the only OS-specific surface is serial port naming (`COM3` vs `/dev/ttyUSB0`), which comes from config.
- **`pyserial`** is the cross-platform serial layer. `printrun` / `printcore` is optional and used
  only inside `printer_serial.py`.
- **Two hardware dependencies**, each with a simulated twin (CLAUDE-COMMON rule 2):
  - Ender-3 V3 SE over USB-C serial → `printer_sim.py`
  - Placer MCU over USB serial → `placer_sim.py`
- **No GPIO on the host.** All physical actuation lives on the placer MCU.
- **Windows sleep must be disabled during a print** — the USB tether has to stay live.
  Use `powercfg /change standby-timeout-ac 0` or presentation mode for the session.

---

## Deployment Notes

The dev machine **is** the runtime machine. "Deployment" here means attaching hardware
and switching entry point — there is no code transfer.

| | Simulation | Hardware run |
|--|-----------|--------------|
| OS | Windows 11 | Windows 11 (same PC) |
| Python | 3.12 venv | 3.12 venv (same) |
| Printer | `links/printer_sim.py` | Ender-3 V3 SE, USB-C, `COM?`, 115200 |
| Placer | `links/placer_sim.py` | ESP32 / Pico, USB, `COM?` (Phase 2) |
| Entry | `python magnet_embed\main_sim.py` | `python magnet_embed\main.py` |

### Pre-hardware checklist (must pass in simulation first)

- [ ] `python -m pytest` — zero failures
- [ ] `main_sim.py` runs a real sliced sample file end-to-end; the sentinel fires a
      simulated place; the print completes
- [ ] Jog / home / set-temp verified against the sim
- [ ] Printer COM port (and placer COM port, Phase 2) identified in Device Manager and
      set in `config.yaml` / `config.local.yaml`
- [ ] Stock firmware backup on hand
- [ ] Magnet grade and polarity-marking procedure decided
- [ ] Windows sleep disabled for the session

### Hardware smoke test

```bat
python -m magnet_embed.links.printer_serial --ping   :: expect firmware banner / ok to M115
python -m magnet_embed.links.placer_serial  --ping   :: expect PONG          (Phase 2)
```

Then: short air-print (Z raised) with a sentinel near layer 2 — head parks, place
fires, print resumes and completes.

### Config differences between simulation and hardware

| Setting | Simulation | Hardware | Where |
|---------|-----------|----------|-------|
| `printer.port` | ignored | `COM?` | `config.yaml` / `config.local.yaml` |
| `placer.port` | ignored | `COM?` | same |
| link classes | `*_sim` | `*_serial` | chosen by entry point |

---

## Known Technical Debt

_None — no code written yet. Record every rule violation here (file + line) as it appears; do not omit._

---

## Development Rules

Referenced by number in TODO items and commit messages.

1. **Dev-machine first.** Every feature is verified against `printer_sim` / `placer_sim`
   before it runs on the printer. (CLAUDE-COMMON — Deployment Model)
2. **Every hardware link has a simulated twin** producing the same return shapes and
   raising the same exception types. (CLAUDE-COMMON)
3. **No hardcoded ports, baud rates, coordinates, or temps** in link/sequence files —
   all from `config.yaml`. (CLAUDE-COMMON)
4. **G-code files stay valid for standalone microSD printing.** The sentinel is a
   comment line, never a real command. (project)
5. **The Insert Magnet sequence leaves the printer resumable on any error** — restore
   nozzle temp, no partial moves, re-raise. No silently swallowed exceptions.
   (PROJ_STARTER — proper error handling)
6. **Minimise pause duration**; nozzle-temp handling during the pause is explicit in
   the sequence. (project — ooze / part-shift risk)
7. **Never drive motion into the part during insertion** — the head parks clear first.
   (project — layer-shift risk)
8. **Tests in `tests/`, `pytest`**, covering the happy path plus key failures
   (ack timeout, sentinel missing, placer `ERR`). (PROJ_STARTER)
9. **venv active for every Python command**; deps pinned in `requirements.txt`;
   flag `uv` when touching packaging. (CLAUDE-COMMON)
10. **Docs updated in the same commit as the code** they describe. (CLAUDE-COMMON)

---

## Project TODO List

> **Authoritative plan: `project/PROJECT_PLAN.md`** — per-phase goals, steps, files
> affected, success criteria, risks, and the consolidated checklist. `TODO.md` mirrors
> the checklist. The list below is the quick view; keep all three in sync in one commit.

Legend: 🔴 Bug / rule violation  |  🟡 Incomplete feature  |  🟢 Not started  |  ✅ Done

### Phase 0 — mechanical proof (no host code)
- 🟢 Design a test part with a magnet pocket (top N layers form the seal cap)
- 🟢 Slice with slicer pause-at-layer (`M0`), insert magnet by hand, verify encapsulation and post-print magnet strength
- 🟢 Decide magnet grade and polarity-marking procedure

### Phase 1 — Python host + Tkinter, operator-triggered place
- 🟢 Repo scaffold: `magnet_embed/` package, venv, `requirements.txt`, `config.yaml`
- 🟢 `PrinterLink` abstract + `printer_sim`
- 🟢 `GcodeRunner`: stream + `ok` handshake + pause/resume/cancel + sentinel detection
- 🟢 `gcode/postprocess.py`: sentinel injection (Cura + PrusaSlicer markers) + CLI
- 🟢 `sequences/insert_magnet.py` with an operator-confirm callback
- 🟢 `ui/panel.py` Tkinter control panel
- 🟢 Tests: runner, postprocess, insert sequence, printer sim
- 🟢 `printer_serial` real link + hardware smoke test on the V3 SE

### Phase 2 — actuated placer MCU
- 🟢 Choose MCU (ESP32 vs Pico) and placer kinematics (servo arm / solenoid + magazine)
- 🟢 MCU firmware: `PING` / `PLACE` serial protocol
- 🟢 `PlacerLink` abstract + `placer_sim` + `placer_serial`
- 🟢 Wire `insert_magnet` to call `placer.place()` instead of the operator prompt
- 🟢 End-to-end hardware run: print → auto-place → encapsulate

### Phase 3 — hardening (later)
- 🟢 Nozzle wipe / temp-drop tuning
- 🟢 Failure recovery (placer jam, magnet missing, mid-pause disconnect)
- 🟢 Multi-magnet parts

---

## User Rules

The full rule set lives in two files in this repo and applies in full:

- **`.CLAUDE/CLAUDE-COMMON.md` → Standard User Rules** — companion files (`TODO.md`,
  `CLAUDE-LOG.md`), the dev-machine-first deployment model, documentation discipline,
  venv / dependency / lint workflow.
- **`.CLAUDE/PROJ_STARTER.md`** — open every response with "ok KLM" + a one-line
  statement of intent; explain every change and wait for explicit confirmation before
  writing files; co-author trailer `Co-authored-by: kl mithunvel <klm@smtw.in>` on
  every commit; DRY, tests, explicit-over-clever, proper error handling, no deprecated
  APIs; Python / Flask / FastAPI / Tkinter / SQLite / YAML / pip+venv (uv planned);
  imperative commit subjects ≤ 72 chars, no vague messages.

Both files are in this repo, so they are referenced rather than duplicated here to
avoid drift. `CLAUDE-COMMON.md` is a shared file — **do not edit it**; raise needed
changes with the owner.

### Project-Specific Overrides

- **Two USB serial devices**, not one: the printer (`printer.port`) and, from Phase 2,
  the placer MCU (`placer.port`). Keep their configuration and their simulated twins
  separate.
- **The printer is a working machine.** Prefer approaches that need no firmware
  reflash. Klipper / custom firmware is out of scope unless the owner reopens it.
- **Safety first in the insert sequence** — Development Rules 5–7 are hard rules, not
  guidelines.
