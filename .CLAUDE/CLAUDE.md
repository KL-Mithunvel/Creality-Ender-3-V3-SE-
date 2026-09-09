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
- **Magnet applicator (add-on):** a **clip-on toolhead add-on** carrying a magnet
  magazine. An **Arduino Uno** (second USB serial port) drives **one servo that
  dispenses a single magnet** onto a holding pole at the tool tip. The **printer's
  own motion** then presses the magnet into the pocket and shears the tool away
  from it. Automation lands in Phase 2; Phase 1 triggers the steps by operator.
- **License:** see `LICENSE` (MIT). **Entry point:** `python main.py`
  (`--sim` default / `--printer` / `--hardware`); the `magnet_embed/main*.py`
  modules stay as back-compat wrappers. **Min runtime:** Python 3.12.

### Working assumptions

- The applicator **clips on and off**. For now, assume it **does not hinder normal
  printing** — no tool-lift servo, no nozzle Z-clearance handling for the add-on.
  Revisit if that assumption breaks.
- Only **one magnet per part** for the prototype (the design keeps room for more).
- The operator is present for every magnet insert.

### Chosen control approach (and the options considered)

| Option | Verdict |
|--------|---------|
| Slicer pause-at-layer only (`M0`), manual insert | **Phase 0** — used to prove the mechanical/encapsulation concept only. No code. |
| Pronterface / Printrun GUI | Bring-up / manual console only, not the product. UX inspiration for our own Tkinter panel (C9–C12), but **no `printrun` dependency and no copied code** — Printrun is GPLv3, this repo is MIT. |
| **Python host script (`pyserial` / `printrun.printcore`) + Tkinter panel** | **Chosen.** Matches the owner's stack, no firmware reflash, runs from the Windows PC. |
| OctoPrint on a Raspberry Pi | Rejected for now — adds a device; no Pi wanted. |
| Klipper + Moonraker | Rejected for now — requires reflashing the printer and losing the stock screen. Revisit only if macro unification becomes compelling. |

---

## Running the System

> Build status: **C1–C8 done — Phase 1 software complete** (`project/BUILD_PLAN.md`).
> Sim pipeline + insert sequence + `postprocess` + Tkinter panel + real serial links
> + per-run logging + integration test; sanity checklist passed. Printer serial link
> verified on real hardware (COM3). **Phase 1.6 (C13–C19) in progress** — one root
> `main.py` (mode by flag), `gcode/toolpath.py`, shared `plan_insert_moves`,
> matplotlib toolpath + insert-motion preview, a "Plan magnet insert" dialog that
> saves `*.magnet.gcode`, plus the panel polish absorbed from C9–C12. **C13 done**
> — root `main.py` + `magnet_embed/entry.py` + raw G-code entry (130 tests). What
> remains for the magnet flow is hardware: build the applicator, wire the Uno,
> measure the offset, run the **manual** hardware smoke test. `.venv` first, always.

```bat
:: one-time setup (Windows) — the project venv is `.venv`
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt    :: uv migration planned — prefer uv when it lands

:: one entry point — mode by flag (--sim default / --printer / --hardware)
python main.py                          :: simulator + GUI — safe on any machine
python main.py --sim tests\data\sample.gcode --no-gui  :: headless sim run
python main.py --printer part.gcode     :: real printer over USB, no dispenser
python main.py --hardware               :: real printer + Arduino dispenser
python main.py --hardware --ping        :: connect to both, report, exit
python main.py --hardware --no-dispenser :: don't build the Uno link
python main.py --preview part.gcode     :: toolpath + insert-motion preview, then exit

:: back-compat module entry points still work (thin wrappers over magnet_embed.entry)
python -m magnet_embed.main_sim --gui tests\data\sample.gcode
python -m magnet_embed.main_printer --ping
python -m magnet_embed.main --ping

:: tests + lint (run before every commit)
python -m pytest
python -m py_compile main.py magnet_embed\*.py

:: G-code prep: inject the magnet sentinel at a layer (or use the panel dialog, C17)
python -m magnet_embed.gcode.postprocess part.gcode --layer 40 --xy 120.5 98 --seat-z 6.2 --shear +X -o part.magnet.gcode
```

Config: `magnet_embed/config.yaml` holds committed defaults; a git-ignored
`magnet_embed/config.local.yaml` is deep-merged over it for real COM ports and the
measured `magnet_tool_offset`.

Simulation vs hardware is selected **by a launch flag**, resolved once in
`magnet_embed/entry.build_links(mode, …)` — `--sim` wires the simulated links,
`--printer` the real printer with **no dispenser** (`dispenser=None`), `--hardware`
both serial links. The links themselves never branch on a mode. All modes read the
same `magnet_embed/config.yaml`. The `magnet_embed/main*.py` modules are thin
back-compat wrappers that call `entry` with a fixed mode.

---

## Architecture

### Module responsibilities

| Path | Role |
|------|------|
| `magnet_embed/config.yaml` | All ports, baud, park/safe-Z, temps, the magnet-tool XYZ offset, press/shear distances + feeds, sentinel token. Nothing hardware-specific is hardcoded elsewhere. |
| `main.py` (repo root) | **The** entry point. `--sim` (default) / `--printer` / `--hardware`; `--ping`, `--no-gui` (headless + `--confirm`), `--no-dispenser`, `--config`. All it does is parse args and call `magnet_embed.entry`. |
| `magnet_embed/entry.py` | Shared wiring: `build_links(mode, config)` → `(printer, dispenser)`; `ping()`; `run_headless()`; `launch_panel()`. One place that constructs links and runs the smoke test. |
| `magnet_embed/main.py` / `main_printer.py` / `main_sim.py` | Back-compat `python -m …` wrappers — each parses its small CLI and calls `entry` with a fixed mode (`hardware` / `printer` / `sim`). The Uno stays optional in `hardware` mode: a dispenser that fails to connect degrades to printer-only for the session. |
| `magnet_embed/state.py` | `PrinterState` dataclass (position, temps, connection, run status) + `MagnetInsert` (parsed sentinel fields). |
| `magnet_embed/links/printer_link.py` | Abstract `PrinterLink` — `connect`, `send_line`, `wait_ok`, `query_state`, `disconnect`. |
| `magnet_embed/links/_marlin_rx.py` | Classify a received line (`ok`/`wait`/`busy`/`resend`/`error`/`action`/`info`) + parse temps / `M114` position. Pure, unit-tested. |
| `magnet_embed/links/printer_serial.py` | `SerialPrinter` — real printer over `pyserial`, 115200, `dtr=False` pre-open, `M115` handshake, `ok`-handshake with `busy`/`wait`/`resend`/`error` handling; `query_state()` = `M400`+`M114`. `--ping` CLI. |
| `magnet_embed/links/printer_sim.py` | Simulated printer — consumes G-code, tracks X/Y/Z/E and temps, emits `ok`, raises the same exceptions as the real link. |
| `magnet_embed/links/dispenser_link.py` | Abstract `DispenserLink` — `ping`, `dispense`, `reset`, `status`. |
| `magnet_embed/links/dispenser_serial.py` | `SerialDispenser` — newline ASCII to the Arduino Uno; rides the ~2 s auto-reset then PINGs to `PONG`; `DISPENSE`/`RESET`/`STATUS`, `ERR…`→`DispenserError`. `--ping` / `--dispense` CLI. |
| `magnet_embed/links/dispenser_sim.py` | Simulated dispenser — returns `OK DISPENSE` / `ERR` like the real Uno. |
| `magnet_embed/gcode/runner.py` | `GcodeRunner` — streams lines, waits for `ok`, detects + parses the sentinel, handles pause / resume / cancel. |
| `magnet_embed/gcode/postprocess.py` | Inserts the `;MAGNET_INSERT X Y Z S<dir>` sentinel comment at a chosen layer / height. |
| `magnet_embed/gcode/toolpath.py` | `parse_toolpath(path) -> Toolpath` — a slice as ordered `Segment`s (travel vs extrude), a layer→Z table (slicer markers, else Z-derived), bounding box, distances, rough time. Feeds the visualisation + the plan dialog. |
| `magnet_embed/viz/toolpath_fig.py` | Pure preview helpers (`nozzle_waypoints`, `pole_waypoints`, `sample_polyline`, `state_at_z`) + matplotlib `draw_*` functions (layer X–Y, side X–Z, 3D path, phase-coloured insert overlay). No GUI backend. |
| `magnet_embed/viz/preview.py` | `PreviewWindow` (Tk `Toplevel`, matplotlib `FigureCanvasTkAgg`) — layer slider, play/scrub the nozzle + pole tip along `plan_insert_moves`, envelope violations flagged, "Open 3D view". `python main.py --preview FILE`. |
| `magnet_embed/sequences/geometry.py` | `compute_targets` / `plan_insert_moves` / `check_envelope` / `pole_point` — the one place the insert-motion targets are computed. `insert_magnet` executes them; the preview + plan dialog draw and envelope-check the same numbers. |
| `magnet_embed/sequences/insert_magnet.py` | The `SAVE → PARK → DISPENSE → APPROACH → PRESS → SHEAR → LIFT → ASK → RESUME` state machine. Targets come from `geometry.compute_targets`. |
| `magnet_embed/app.py` | `Controller` — headless UI↔worker mediator (threads, queues, prompt blocking); optional `log_dir` writes a per-run transcript. |
| `magnet_embed/runlog.py` | `RunLog` — one `logs/<ts>-<name>.log` per streamed job, a timestamped line per event. |
| `magnet_embed/ui/panel.py` | Tkinter panel — thin view over `Controller`; jog/home + raw G-code entry idle-only, "Plan magnet insert…" dialog, modal Success/Retry/Abort prompt, live log. |
| `magnet_embed/ui/plan_dialog.py` | "Plan magnet insert" dialog + pure helpers — set pocket X/Y, seat Z, shear, target layer/Z; envelope-check; Preview; **Save `<stem>.magnet.gcode`** and load it. |
| `dispenser_fw/` | Arduino Uno sketch for the magazine servo (Phase 2). |
| `tests/` | `pytest` — runner, postprocess, insert state machine, printer sim, dispenser sim. |

### Data flow

```
Creality Print / Cura ──slice──► part.gcode
                                     │
   gcode/postprocess.py inserts  ";MAGNET_INSERT X Y Z S<dir>"  at layer N
                                     │
                                     ▼
   ┌──────────────── host: Windows 11 PC (Python) ─────────────────┐
   │  ui/panel.py ─► gcode/runner.py ─► links/printer_serial ──────┼─USB-C 115200─►  Ender-3 V3 SE
   │                       │                                       │   (press + shear = printer moves)
   │      on ";MAGNET_INSERT …":                                   │
   │                       └─► sequences/insert_magnet ────────────┤
   │                                   │                           │
   │                                   └─► links/dispenser_serial ─┼─USB serial──►  Arduino Uno ─► magazine servo
   └──────────────────────────────────────────────────────────────┘                                   [Phase 2]
```

### Insert sequence (state machine)

Fired when `GcodeRunner` sees the sentinel; streaming is paused (the printer just
holds position and temp — no `M0`/`M25`). Full detail with tunable values in
`project/PROJECT_PLAN.md` → Phase 2.

```
SAVE      record X Y Z E, feedrates, G90/G91, M82/M83, nozzle + bed temp
PARK      M83; retract 2–5 mm; Z-hop to safe clearance; nozzle → standby_nozzle_temp_c (bed stays hot)
DISPENSE  dispenser.dispense()  (Phase 1: operator prompt) — magnet moves to the holding pole
APPROACH  move XY to  pocket_xy − magnet_tool_offset.xy  at safe Z;  host envelope check → abort if outside
PRESS     Z down to  seat_z − magnet_tool_offset.z  at press.feed;  brief dwell
SHEAR     lateral move shear.distance in shear_dir at shear.feed — pole slides off the seated magnet
LIFT      Z to safe clearance;  move clear of the part
ASK       prompt() → "success" | "retry" | "abort"
           retry → operator makes safe, then re-run from DISPENSE (or APPROACH if the magnet is still on the pole)
           abort → heaters to safe, print stays paused (resumable) or cancelled
RESUME    nozzle → print temp, M109;  XY → saved pos at safe Z;  Z → saved Z;
          un-retract; prime + wipe; restore G90 / M82 / feedrates
```

No `G28` anywhere — every move after `SAVE` is commanded and tracked (Dev Rule 11).

### Threading model

- Tkinter main loop on the main thread.
- G-code streaming on one worker thread (`GcodeRunner.run()`).
- Each serial link has its own reader thread.
- Threads talk to the UI through a thread-safe queue polled via `root.after(...)`.
  No Tkinter calls off the main thread.

### Simulation vs real

Chosen by entry point. `printer_sim` / `dispenser_sim` produce the same return
shapes and raise the same exception types as the serial links, so `GcodeRunner`,
`insert_magnet`, and the UI are exercised end-to-end on the dev machine with no
hardware attached.

---

## Key Modules

> Built (C1–C5): everything below. Not built: the C6 integration test + run
> logging; the manual hardware smoke test.
> Actual layout: text/number helpers are in `gcode/util.py`; both ABCs in
> `links/base.py`; the Marlin receive-line classifier is `links/_marlin_rx.py`;
> the UI↔worker mediator is `app.Controller`, not inside `ui/`.

### `links/printer_link.py` — `PrinterLink` (abstract)
- `connect() -> None` — open the port, wait for the firmware banner. Raises `PrinterConnectionError`.
- `send_line(line: str) -> None` — write one G-code line (no newline needed).
- `wait_ok(timeout_s: float) -> str` — block until `ok`; return any payload (temps). Raises `AckTimeout`.
- `query_state() -> PrinterState`.
- `disconnect() -> None`.
- I/O: serial port from `config.yaml`.

### `links/dispenser_link.py` — `DispenserLink` (abstract)
- `ping() -> bool` — `PING` → `PONG`.
- `dispense() -> None` — feed one magnet to the holding pole. Raises `DispenserError` on `ERR DISPENSE <reason>`.
- `reset() -> None` — servo to home / loaded position.
- `status() -> dict` — servo angle, dispensed count, last command.
- I/O: second serial port (Arduino Uno) from `config.yaml`. The real link waits out
  the Uno's ~2 s auto-reset after `connect()` and `PING`s until `PONG`.

### `gcode/runner.py` — `GcodeRunner`
- `__init__(link: PrinterLink, gcode_path: str, on_sentinel: Callable[[MagnetInsert], None], config: dict)`.
- `run() -> None` — stream every line, `wait_ok` after each; when a stripped line starts with the
  sentinel token, parse it into a `MagnetInsert` and call `on_sentinel(mi)` instead of sending it.
- `pause()`, `resume()`, `cancel()` — thread-safe.
- Side effects: reads the G-code file, writes to the printer link, appends to the run log.
- Exceptions: `AckTimeout`, `SentinelNotFound` (if `require_sentinel` and EOF reached first), `SentinelParseError`.

### `gcode/postprocess.py`
- `inject_sentinel(in_path, out_path, *, layer: int | None, z_mm: float | None,
  pocket_xy: tuple[float, float], seat_z: float, shear: str, emit_pause: bool = False) -> int`
  — inserts `;MAGNET_INSERT X<px> Y<py> Z<seat_z> S<shear>` at the chosen layer and
  returns the sentinel's line number. `emit_pause` also writes a real `M0` just
  before it (so microSD prints pause too). Coordinates are in bed space.
- Understands Cura / Creality Print (`;LAYER:<n>`) and PrusaSlicer (`;LAYER_CHANGE` + `;Z:<h>`) markers.
- CLI: `python -m magnet_embed.gcode.postprocess <file> (--layer N | --z H) --xy PX PY --seat-z SZ --shear +X|-X|+Y|-Y [--pause] [-o OUT]`.
- Or use the panel's **Plan magnet insert…** dialog (`ui/plan_dialog.py`).

### `ui/plan_dialog.py`
- `PlanInsertDialog` + pure helpers `resolve_target_z`, `magnet_output_path`,
  `save_magnet_gcode`, `envelope_report`. Enter pocket X/Y, seat Z, shear, and a
  target (layer index or Z height); live envelope check; **Preview** opens the C16
  window; **Save** writes `<stem>.magnet.gcode` and loads it as the active file.

### `sequences/geometry.py`
- `compute_targets(mi, config, saved) -> Targets` (`approach_xy`, `press_z`,
  `shear_xy`, `safe_z`), `plan_insert_moves(mi, config, saved) -> list[InsertMove]`
  (nozzle-tip waypoints, phase-tagged), `check_envelope(mi, config, saved) -> list[str]`,
  `pole_point(nozzle, config) -> Point`.
- Pure. `insert_magnet` builds its targets here; the C16 preview and C17 dialog draw
  and envelope-check the *same* function output — the preview cannot drift from the run.

### `sequences/insert_magnet.py`
- `insert_magnet(printer: PrinterLink, dispenser: DispenserLink | None, mi: MagnetInsert,
  config: dict, prompt: Callable[[str], str]) -> None`
  — `mi` carries the parsed sentinel fields; `prompt("dispense")` returns
  `"ready" | "abort"` (only used when `dispenser` is `None`), `prompt("confirm")`
  returns `"success" | "retry" | "abort"`.
- Targets from `geometry.compute_targets`; envelope from `geometry.check_envelope`
  (raises `OutOfEnvelopeError` if non-empty). Runs the state machine in
  Architecture → Insert sequence; every phase gated with `M400`.
- Raises `OutOfEnvelopeError` (before any move), `SequenceAborted`, or the dispenser's error.
- **No `G28` anywhere** — every move is commanded and tracked (Development Rule 11).
- On any failure: nozzle target restored (or set to 0 on operator abort), re-raised. Never swallowed.

### `app.py` — `Controller`
- Headless mediator (no Tkinter). Owns `printer`, `dispenser`, `config`, the
  `GcodeRunner`, and two queues. `start_run()` spawns a daemon worker;
  worker→UI events via `poll_events()`; the insert sequence's `prompt()` blocks the
  worker on an answers queue until `answer_prompt(value)`.
- `dispenser_optional=True` (used by `--hardware`): if `dispenser.connect()` raises a
  `DispenserError`, `connect()` logs it, drops `self.dispenser` to `None`, and does
  not raise — the run continues printer-only. Default `False` keeps it strict.
- Actions: `connect`, `load_gcode`, `jog`, `home`, `set_temp`, `send_command` (raw
  G-code line; all no-ops while a run is active), `start_run`, `pause`, `resume`,
  `cancel`, `answer_prompt`.
- Event kinds: `log`, `state` (a `PrinterState`), `prompt` (`"dispense"`/`"confirm"`),
  `done`, `error`.

### `ui/panel.py` — `ControlPanel` + `run_gui(controller)`
- Thin Tkinter view over a `Controller`. Connect, load G-code, run/pause/resume/cancel,
  jog (0.1/1/10 mm) + home + raw G-code entry **idle only**, set temps, read-only log,
  live position/temp line. `_show_prompt` opens a modal **Success / Retry / Abort**
  (or **Ready / Abort**) dialog that calls `controller.answer_prompt`. Drains
  `poll_events()` every 120 ms.

---

## Key Conventions

- **Magnet sentinel — `;MAGNET_INSERT X<px> Y<py> Z<seat_z> S<dir>`.** A G-code
  **comment** line inserted by `gcode/postprocess.py` at the chosen layer, so the file
  still prints unchanged straight from microSD. Fields:
  - `X`, `Y` — pocket centre in bed coordinates
  - `Z` — magnet seat height (pocket floor + magnet thickness)
  - `S` — shear direction, one of `+X -X +Y -Y` (the way with clearance to slide the pole off)

  `GcodeRunner` matches the line by prefix (after `.strip()`) against
  `config['gcode']['sentinel_token']` (default `;MAGNET_INSERT`), parses the fields into
  a `MagnetInsert`, fires the insert sequence, and does **not** send the line to the printer.
- **Magnet-tool offset.** `magnet_tool_offset: {x, y, z}` is **(holding-pole tip) −
  (nozzle tip)**, measured empirically with signs. `+z` means the pole tip sits above
  the nozzle tip. `insert_magnet` drives the carriage to `pocket_xy − (offset.x,
  offset.y)` and presses the nozzle down to `seat_z − offset.z` (so the pole tip lands
  at `seat_z`). The offset shrinks the reachable area and can make a low pocket
  unreachable (`seat_z − offset.z < 0`) — the host checks every target in-envelope and
  **aborts the sequence with the print still paused** if not.
- **Press and shear are printer moves, not servo moves.** The Arduino servo only
  *dispenses* one magnet to the holding pole. The **printer** presses (Z down to seat
  depth) and shears (short **lateral** move so the pole slides off the seated magnet).
  Shear is lateral — never straight up — so the magnet is not pulled back out of the pocket.
- **Layer / height targeting.** `postprocess` finds the insertion point from slicer
  markers: `;LAYER:<n>` (Cura / Creality Print) or `;LAYER_CHANGE` + `;Z:<height>`
  (PrusaSlicer). `--layer` matches the marker index; `--z` the first layer with height ≥ value.
- **Dispenser (Arduino Uno) protocol** — newline-terminated ASCII, deliberately dumb:
  - host → Uno: `PING`, `DISPENSE`, `RESET`, `STATUS`
  - Uno → host: `PONG`, `OK DISPENSE`, `OK RESET`, `STATUS servo=<deg> count=<n> last=<cmd>`,
    `ERR DISPENSE <reason>`, `WARN IDLE` (watchdog safed the servo after host silence)
  - Opening the port resets the Uno (~2 s bootloader); the host waits, flushes, then
    `PING`s until `PONG` before trusting it.
- **Config precedence.** Everything hardware-specific — COM ports, baud, `park_xy`,
  `safe_z_lift_mm`, `standby_nozzle_temp_c`, `magnet_tool_offset`, `press.*`, `shear.*`,
  `sentinel_token` — lives in `magnet_embed/config.yaml` and is passed as parameters.
  Simulated links ignore the port keys. No hardcoded ports, coordinates, or temps in
  link / sequence files.
- **Magnet polarity is deterministic** — the holding pole forces each dispensed
  magnet's orientation, so a consistently loaded magazine yields consistent polarity in
  the part. No per-magnet marking; verify the magazine loading direction instead.
- **Pause hygiene.** Retract before parking; drop the nozzle to `standby_nozzle_temp_c`
  during the pause / operator prompt; keep the bed hot; un-retract + prime + wipe on
  resume. Keep the pause as short as the operator check allows.

---

## Data Files

| File | Tracked? | Notes |
|------|----------|-------|
| `.CLAUDE/*.md`, `project/*.md`, `docs/*.md`, `README.md`, `TODO.md` | yes | Project docs. `CLAUDE-COMMON.md` is shared — never edit here. `HOW_IT_WORKS.md` = plain-language guide; `RESEARCH.md` = prior-art survey; `BUILD_PLAN.md` = chunk plan; `docs/INVENTION_DISCLOSURE_DRAFT.md` = patent-form draft. |
| `docs/*.docx` | yes | Supplied forms/templates (e.g. the K&K invention disclosure form). `~$*` lock files are git-ignored. |
| `.gitignore` | yes | Excludes `.idea/`, `venv/`, `__pycache__/`, generated G-code, `logs/`, `config.local.yaml`. |
| `magnet_embed/config.yaml` | yes | Committed with safe defaults; local COM ports / offsets may be overridden — see below. |
| `dispenser_fw/` | yes | Phase 2 — Arduino Uno sketch for the magazine servo. |
| `*.gcode`, `*.magnet.gcode` | **no** — gitignore | Sliced parts and post-processed output. Generated, not committed. |
| `logs/*.log` | **no** — gitignore | Per-run serial transcripts. |
| `requirements.txt` | yes | Pinned deps (`pip freeze` after installs). |

If a local machine needs different COM ports or a tuned offset, use a gitignored
`config.local.yaml` (loaded over `config.yaml` when present) rather than editing the
tracked file.

---

## Platform Constraints

- **Host OS:** Windows 11 (the owner's machine). Code should also run on Linux / Raspberry Pi OS —
  the only OS-specific surface is serial port naming (`COM3` vs `/dev/ttyUSB0`), which comes from config.
- **`pyserial`** is the cross-platform serial layer (imported lazily inside the
  `*_serial.py` modules; the sims and the tests don't need it — tests inject a fake
  transport). `printrun` / `printcore` is **not** a dependency — the streaming loop is
  our own (`GcodeRunner` + `SerialPrinter`).
- **Two hardware dependencies**, each with a simulated twin (CLAUDE-COMMON rule 2):
  - Ender-3 V3 SE over USB-C serial → `printer_sim.py`
  - Arduino Uno (magazine servo) over USB serial → `dispenser_sim.py`
- **No GPIO on the host.** All actuation is either a printer G-code move or the Uno's servo.
- **Arduino Uno quirks:** opening the serial port auto-resets the board (~2 s); the servo
  needs its own 5–6 V supply (not the Uno's regulator) with a common ground; the sketch
  runs a watchdog that safes the servo if the host goes quiet.
- **Magnets near steel:** the V3 SE bed is a magnetic spring-steel flex plate and the
  hotend is steel — keep the magnet held by the pole until sheared, and bench-test how
  close it can get to the plate before it snatches.
- **Windows sleep must be disabled during a print** — the USB tether has to stay live.
  Use `powercfg /change standby-timeout-ac 0` or presentation mode for the session.

---

## Deployment Notes

The dev machine **is** the runtime machine. "Deployment" here means attaching hardware
and passing a different launch flag — there is no code transfer.

| | Simulation | Printer only | Full hardware |
|--|-----------|--------------|--------------|
| OS | Windows 11 | Windows 11 (same PC) | Windows 11 (same PC) |
| Python | 3.12 `.venv` | 3.12 `.venv` (same) | 3.12 `.venv` (same) |
| Printer | `links/printer_sim.py` | Ender-3 V3 SE, USB-C, `COM3`, 115200 | Ender-3 V3 SE, USB-C, `COM3`, 115200 |
| Dispenser | `links/dispenser_sim.py` | none (`dispenser=None`) | Arduino Uno, USB, `COM?` (Phase 2) |
| Launch | `python main.py` | `python main.py --printer` | `python main.py --hardware` |

### Pre-hardware checklist (must pass in simulation first)

- [ ] `python -m pytest` — zero failures
- [ ] `main_sim.py` runs a real sliced sample file end-to-end; the sentinel fires the
      full insert state machine; the print completes
- [ ] Jog / home / set-temp verified against the sim
- [ ] Printer COM port (and Arduino Uno COM port, Phase 2) identified in Device Manager
      and set in `config.yaml` / `config.local.yaml`
- [ ] Magnet-tool XYZ offset measured and in config; shear direction has real clearance
- [ ] Magnet grade decided; magazine loaded consistently (polarity is set by the holding pole)
- [ ] Stock firmware backup on hand
- [ ] Windows sleep disabled for the session

### Hardware smoke test

```bat
python main.py --hardware --ping                        :: both devices at once
python main.py --printer --ping                         :: printer only
python -m magnet_embed.links.printer_serial    --ping   :: printer only (M115 -> ok)
python -m magnet_embed.links.dispenser_serial  --ping   :: Uno only (-> PONG)   (Phase 2)
```

**Printer link verified on real hardware 2026-09-09** (`printer_serial --ping` on
COM3 — `M115`/`M400`/`M114` OK). The Uno and applicator are not built yet; use
`python main.py --printer` for real prints in the meantime.

Then: short air-print (Z raised, no filament) with a sentinel near layer 2 — head
parks, magnet dispensed, controlled press + lateral shear run, print resumes and completes.

### Config differences between simulation and hardware

| Setting | Simulation | Hardware | Where |
|---------|-----------|----------|-------|
| `printer.port` | ignored | `COM?` | `config.yaml` / `config.local.yaml` |
| `dispenser.port` | ignored | `COM?` | same |
| `magnet_tool_offset` | any value | measured | `config.local.yaml` |
| link classes | `*_sim` | `*_serial` | chosen by entry point |

---

## Known Technical Debt

- **No hardware validation yet.** The whole stack is proven against `SimPrinter` /
  `SimDispenser` (94 tests) but has never driven the real printer or a real Uno. The
  first hardware run may surface firmware-serial quirks (the Ender-3 V3 SE has known
  OctoPrint friction) and mechanism issues. Treat the first bench session as
  debugging, not production.
- **Tool offset / press depth / shear params in `config.yaml` are guesses.** They must
  be measured on the real machine (`config.local.yaml`) — see `PROJECT_PLAN.md` §8.
- **`dispenser_fw/` (the Arduino sketch) does not exist yet.** `SerialDispenser`
  assumes the `PING`/`DISPENSE`/… protocol; the sketch must implement it.

No rule violations recorded. Add any here (file + line) as they appear; do not omit.

---

## Development Rules

Referenced by number in TODO items and commit messages.

1. **Dev-machine first.** Every feature is verified against `printer_sim` / `dispenser_sim`
   before it runs on the printer. (CLAUDE-COMMON — Deployment Model)
2. **Every hardware link has a simulated twin** producing the same return shapes and
   raising the same exception types. (CLAUDE-COMMON)
3. **No hardcoded ports, baud rates, coordinates, or temps** in link/sequence files —
   all from `config.yaml`. (CLAUDE-COMMON)
4. **G-code files stay valid for standalone microSD printing.** The sentinel is a
   comment line, never a real command. (project)
5. **The insert sequence leaves the printer resumable on any error** — restore nozzle
   temp, no partial moves, re-raise. No silently swallowed exceptions.
   (PROJ_STARTER — proper error handling)
6. **Minimise pause duration**; nozzle-temp handling during the pause is explicit in
   the sequence. (project — ooze / part-shift risk)
7. **Only the magnet tool contacts the part during insertion** — the nozzle parks clear
   first; the only commanded contact moves are the controlled `PRESS` (Z to seat depth
   at `press.feed`) and the lateral `SHEAR`. (project — layer-shift / damage risk)
8. **Tests in `tests/`, `pytest`**, covering the happy path plus key failures
   (ack timeout, sentinel missing / unparseable, dispenser `ERR`, out-of-envelope target). (PROJ_STARTER)
9. **venv active for every Python command**; deps pinned in `requirements.txt`;
   flag `uv` when touching packaging. (CLAUDE-COMMON)
10. **Docs updated in the same commit as the code** they describe. (CLAUDE-COMMON)
11. **No `G28` / homing during a print.** After `SAVE`, every move is commanded and
    tracked; return to the saved coordinates. Homing mid-print risks driving the nozzle
    through the part. (project — collision risk)
12. **The insert target must be in-envelope after the tool offset is applied** — the
    sequence checks and aborts (print stays paused) rather than commanding an
    out-of-range move. (project)
13. **Press + shear logic lives on the host, not the Uno.** The Arduino sketch only
    dispenses; keep it dumb. (project)

---

## Project TODO List

> **Authoritative plan: `project/PROJECT_PLAN.md`** — per-phase goals, steps, files
> affected, success criteria, risks, and the consolidated checklist. **Software build
> is chunked in `project/BUILD_PLAN.md`** (C1–C6, one commit each, with protocol notes
> and research references). `TODO.md` mirrors the checklists. The list below is the
> quick view; keep them in sync in one commit.

Legend: 🔴 Bug / rule violation  |  🟡 Incomplete feature  |  🟢 Not started  |  ✅ Done

### Phase 0 — mechanical proof (no host code)
- 🟢 Design a test part with a magnet pocket (top N layers form the seal cap)
- 🟢 Slice with slicer pause-at-layer (`M0`), insert magnet by hand, verify encapsulation and post-print magnet strength
- 🟢 Decide magnet grade; settle pocket retention strategy (press-fit / adhesive / stripper)

### Phase 1 — Python host + Tkinter, operator-triggered steps
- 🟢 Repo scaffold: `magnet_embed/` package, venv, `requirements.txt`, `config.yaml`
- 🟢 `PrinterLink` abstract + `printer_sim`
- 🟢 `GcodeRunner`: stream + `ok` handshake + pause/resume/cancel + sentinel detect & parse
- 🟢 `gcode/postprocess.py`: `;MAGNET_INSERT X Y Z S<dir>` injection (Cura + PrusaSlicer markers) + CLI
- 🟢 `sequences/insert_magnet.py` state machine with operator prompts standing in for the Uno
- 🟢 `ui/panel.py` Tkinter panel incl. the Success / Retry / Abort prompt
- 🟢 Tests: runner, postprocess, insert state machine, printer sim
- 🟢 `printer_serial` real link + hardware smoke test on the V3 SE

### Phase 2 — magnet applicator (Arduino Uno + printer moves)
- 🟢 Finalise applicator mechanics: magazine escapement, holding-pole strength vs pocket retention
- 🟢 Measure the magnet-tool XYZ offset; pick shear distance + direction
- 🟢 Arduino Uno sketch: `PING` / `DISPENSE` / `RESET` / `STATUS` + idle watchdog
- 🟢 `DispenserLink` abstract + `dispenser_sim` + `dispenser_serial` (handles Uno auto-reset)
- 🟢 Wire `dispenser.dispense()` into the `DISPENSE` state, operator prompt as fallback
- 🟢 Bench tests: servo alone, cold "air insert", magnet-near-plate, idle-heater timeout
- 🟢 End-to-end hardware run: print → dispense → press → shear → operator OK → resume

### Phase 3 — hardening (later)
- 🟢 Nozzle wipe / temp-drop tuning
- 🟢 Failure recovery (magazine jam, magnet missing, mid-pause disconnect)
- 🟢 Multi-magnet parts (multiple sentinels, per-sentinel park + shear)
- 🟢 Optional hall sensor to confirm deposit instead of the operator check

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
  the Arduino Uno dispenser (`dispenser.port`). Keep their config and simulated twins separate.
- **Press + shear are printer moves; the Uno only dispenses.** Don't push press/shear
  logic into the Arduino sketch (Development Rule 13).
- **The applicator is a clip-on add-on.** For now assume it clips on and does not hinder
  normal printing (no tool-lift servo, no nozzle Z-clearance handling). Revisit if that breaks.
- **The printer is a working machine.** Prefer approaches that need no firmware reflash.
  Klipper / custom firmware is out of scope unless the owner reopens it.
- **Safety first in the insert sequence** — Development Rules 5–7 and 11–12 are hard
  rules, not guidelines.
