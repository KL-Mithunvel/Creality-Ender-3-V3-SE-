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

> Build status: **C1–C8 + Phase 1.6 (C13–C19) + Phase 1.7 (C20) + Phase 1.8
> (C21) + Phase 1.9 (C22) + Phase 1.10 (C23) + Phase 1.11 (C24) + Phase 1.12
> (C25: nozzle-vs-part collision guard + Emergency Stop) + Phase 1.13 (C26:
> insert-phase live view) + Phase 1.14 (C27: safe-cancel + off-thread
> Home/Level Bed/Z-cal) + Phase 1.15 (C28: Connect/Disconnect toggle) +
> Phase 1.16 (C29: opt-in line-numbered/checksummed streaming + resend
> buffer + `M420 S1` resend-after-`G28`) + Phase 1.17 (C30: collision guard
> restricted to already-printed layers) + Phase 1.18 (C31: GUI performance
> fixes — Animate tick stops when not playing, 3D redraw throttled slower
> than 2D — plus a UX pass: Pause/Resume as one toggle, human-readable
> "run finished" line, 3D defaults to Local, Plan dialog seat-Z default
> tied to the insert layer, fixed double-wrapped dialog text, bigger jog
> targets + arrow-key jog) done, plus mid-print temp control, a Level Bed
> button, a run-report summary in the log, in-panel config editing, an
> embedded live-print view showing 2D and equal-scale bed-aware 3D side by
> side with a Global-bed/Local-part crop toggle, a guided Z-offset
> calibration dialog, and a two-column panel that opens maximized and shows
> what it's actually connected to — 262 tests** (`project/BUILD_PLAN.md`).
> One root `python main.py` (mode by flag), `gcode/toolpath.py`, shared
> `sequences/geometry.py`, a matplotlib toolpath + insert-motion preview
> (`main.py --preview`), a "Plan magnet insert…" dialog that saves
> `*.magnet.gcode` and embeds a live preview of the insert motion, the panel
> polish (raw G-code, idle poll, extrude/retract, progress bar), and a
> live-print view in the main panel (current layer + isometric 3D side by
> side, the 3D path growing as the nozzle passes through it, plus a
> nozzle marker driven from G-code line progress, no extra printer traffic).
> `GcodeRunner` skips firmware-pause codes (`M0`/`M1`/`M25`/`M600`/`M601`).
> Printer serial link verified on real hardware (COM3). What remains for the magnet
> flow is hardware: build the applicator, wire the Uno, measure the offset, run the
> **manual** hardware smoke test. `.venv` first, always.

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
| `magnet_embed/config.yaml` | All ports, baud, park/safe-Z, temps (incl. `nozzle_min_c`/`nozzle_max_c`/`bed_min_c`/`bed_max_c` guard rails for `set_temp`), the magnet-tool XYZ offset, press/shear distances + feeds, `collision.*` (`nozzle_clearance_mm` the nozzle must keep above the printed top while over the part, `footprint_margin_mm` grown around the part's bbox — the C25 damage guard), `cancel.heaters_off` (C27: whether `Controller.cancel()`'s safe-cancel retreat turns the heaters off), sentinel token, `gcode.use_line_numbers`/`gcode.resend_leveling_after_home` (C29, both opt-in and unverified on hardware), `zcal.*` (Z-offset calibration point/step/feed and the trusted `probe_z_offset`). Nothing hardware-specific is hardcoded elsewhere. |
| `main.py` (repo root) | **The** entry point. `--sim` (default) / `--printer` / `--hardware`; `--ping`, `--no-gui` (headless + `--confirm`), `--no-dispenser`, `--config`. All it does is parse args and call `magnet_embed.entry`. |
| `magnet_embed/entry.py` | Shared wiring: `build_links(mode, config)` → `(printer, dispenser)`; `ping()`; `run_headless()`; `launch_panel()`. One place that constructs links and runs the smoke test. |
| `magnet_embed/main.py` / `main_printer.py` / `main_sim.py` | Back-compat `python -m …` wrappers — each parses its small CLI and calls `entry` with a fixed mode (`hardware` / `printer` / `sim`). The Uno stays optional in `hardware` mode: a dispenser that fails to connect degrades to printer-only for the session. |
| `magnet_embed/state.py` | `PrinterState` dataclass (position, temps, connection, run status) + `MagnetInsert` (parsed sentinel fields). |
| `magnet_embed/links/printer_link.py` | Abstract `PrinterLink` — `connect`, `send_line`, `wait_ok`, `query_state`, `disconnect`. |
| `magnet_embed/links/_marlin_rx.py` | Classify a received line (`ok`/`wait`/`busy`/`resend`/`error`/`action`/`info`) + parse temps / `M114` position. Pure, unit-tested. |
| `magnet_embed/links/printer_serial.py` | `SerialPrinter` — real printer over `pyserial`, 115200, `dtr=False` pre-open, `M115` handshake, `ok`-handshake with `busy`/`wait`/`resend`/`error` handling; `query_state()` = `M400`+`M114`. `--ping` CLI. `_track_outgoing` strips a numbered-line wrapper (`gcode.util.strip_line_number`, C29) before parsing modal state. |
| `magnet_embed/links/printer_sim.py` | Simulated printer — consumes G-code, tracks X/Y/Z/E and temps, emits `ok`, raises the same exceptions as the real link. Accepts plain or `N<n> ...*<checksum>` lines (C29) — strips the wrapper before parsing, same as real Marlin. |
| `magnet_embed/links/dispenser_link.py` | Abstract `DispenserLink` — `ping`, `dispense`, `reset`, `status`. |
| `magnet_embed/links/dispenser_serial.py` | `SerialDispenser` — newline ASCII to the Arduino Uno; rides the ~2 s auto-reset then PINGs to `PONG`; `DISPENSE`/`RESET`/`STATUS`, `ERR…`→`DispenserError`. `--ping` / `--dispense` CLI. |
| `magnet_embed/links/dispenser_sim.py` | Simulated dispenser — returns `OK DISPENSE` / `ERR` like the real Uno. |
| `magnet_embed/gcode/runner.py` | `GcodeRunner` — streams lines, waits for `ok`, detects + parses the sentinel, drops firmware-pause codes (`M0`/`M1`/`M25`/`M600`/`M601`), handles pause / resume / cancel. With `config.gcode.use_line_numbers` (C29, opt-in, off by default) sends `N<n> ...*<checksum>` lines and replays a small buffer on a firmware `Resend:` instead of aborting; with `config.gcode.resend_leveling_after_home` (opt-in) re-sends `M420 S1` right after any streamed `G28`. |
| `magnet_embed/gcode/postprocess.py` | Inserts the `;MAGNET_INSERT X Y Z S<dir>` sentinel comment at a chosen layer / height. |
| `magnet_embed/gcode/toolpath.py` | `parse_toolpath(path) -> Toolpath` — a slice as ordered `Segment`s (travel vs extrude, each carrying a 1-based `line_no`), a layer→Z table (slicer markers, else Z-derived), bounding box, distances, rough time. `progress_position(current_line)` / `progress_layer(current_line)` bisect the parsed path to the nozzle position/layer implied by how far `GcodeRunner` has streamed — no extra printer traffic. Feeds the visualisation, the plan dialog, and the panel's live-print view. |
| `magnet_embed/viz/toolpath_fig.py` | Pure preview helpers (`nozzle_waypoints`, `pole_waypoints`, `sample_polyline`, `state_at_z`, `progressive_path_3d`) + matplotlib `draw_*` functions (layer X–Y, side X–Z, 3D path, phase-coloured insert overlay, `draw_live_layer`/`update_live_marker` for the panel's 2D live view + `draw_live_3d(..., show_bed=)`/`update_live_3d`/`update_live_3d_marker` (C26: moves just the 3D marker, without redrawing the growing path — used when the nozzle position comes from the insert-phase waypoints rather than line progress) for the 3D one — `show_bed=True` spans the real bed with the plate outline, `show_bed=False` crops tight to the part; both use explicit `set_xlim`/`set_ylim`/`set_zlim` + `set_box_aspect` for equal-scale axes with no autoscale-margin surprises, plus a path that grows as the nozzle passes through it). No GUI backend. |
| `magnet_embed/viz/preview.py` | `PreviewWindow` (Tk `Toplevel`, matplotlib `FigureCanvasTkAgg`) — layer slider, play/scrub the nozzle + pole tip along `plan_insert_moves`, envelope violations flagged, "Open 3D view". `python main.py --preview FILE`. The 40 ms `_tick` loop (C31) only reschedules itself while `self.playing` — previously it kept ticking for as long as the window stayed open, playing or not, one of two measured contributors to "system feels slow" (see `ui/panel.py` Key Modules for the other, the 3D redraw throttle). |
| `magnet_embed/sequences/geometry.py` | `compute_targets` / `plan_insert_moves` / `check_envelope(mi, config, saved, toolpath=None)` / `part_footprint` / `pole_point` — the one place the insert-motion targets are computed **and the one damage guard** (C25): pocket on the bed, nozzle targets inside the machine limits, no press into the build plate, and — with the toolpath — no press/shear that puts the nozzle inside the printed part, tested against only the layers already printed at insert time (`_printed_footprint`, C30) rather than the whole file. `insert_magnet` executes the targets; the preview + plan dialog draw and check the same numbers. |
| `magnet_embed/sequences/insert_magnet.py` | The `SAVE → PARK → DISPENSE → APPROACH → PRESS → SHEAR → LIFT → ASK → RESUME` state machine. Targets come from `geometry.compute_targets`; `toolpath=` (keyword) enables the collision guard — every caller that has the file passes it. `on_phase=` (keyword, C26) fires once per phase with its exact nozzle-tip target (`None` for the two non-motion phases), from the same values the phase actually sends — a live-view caller can't drift from the run. |
| `magnet_embed/app.py` | `Controller` — headless UI↔worker mediator (threads, queues, prompt blocking); optional `log_dir` writes a per-run transcript. `load_gcode()` caches a parsed `toolpath` + raw `gcode_lines` (best-effort — a parse failure logs and leaves them empty rather than blocking the load); `progress_point`/`current_line_text` derive the live nozzle position + current G-code line from them. `start_z_calibration()`/`nudge_z()`/`save_z_offset()` drive the Z Calibrate dialog (idle-only). `link_summary` → `"simulator"` / `"printer COM3"` / `"... + dispenser COM4"`, from whether the link objects have a `.port` (real) or not (sim). `in_insert` (read-only property, C26) + `_on_insert_phase` wire `insert_magnet`'s `on_phase` into a new `"phase"` event kind so the panel can show live progress during an insert instead of freezing at the sentinel. |
| `magnet_embed/runlog.py` | `RunLog` — one `logs/<ts>-<name>.log` per streamed job, a timestamped line per event, plus a human-readable `=== SUMMARY ===` block appended on `close()` (duration, lines sent/total, sentinels seen, any errors, final position + temps). `summary_text` is also echoed to the panel log right after a run finishes. |
| `magnet_embed/ui/panel.py` | Tkinter panel — thin view over `Controller`; a two-column layout (jog/temperature/filament left, live view + send-G-code + log right, right column stretches to fill the window) wrapped in a scrollable canvas as a fallback so nothing clips on a screen too small even maximized; `run_gui()` opens maximized by default; shows a mode/port label (`Controller.link_summary`) next to the connection status; jog/home/Level-Bed/Z-Calibrate + raw G-code entry idle-only, "Plan magnet insert…", "Settings…", and "Z Calibrate…" dialogs, modal Success/Retry/Abort prompt, live log, an embedded live-print view showing the current layer (2D) and an isometric 3D view **side by side** with a "Global bed" / "Local part" crop toggle + nozzle marker + current-step G-code text. During a magnet insert (`Controller.in_insert`, C26) the marker and "current step" label switch to the latest `"phase"` event instead of frozen line progress; the 2D layer and 3D path stay frozen at the sentinel rather than being recomputed. |
| `magnet_embed/ui/plan_dialog.py` | "Plan magnet insert" dialog + pure helpers — set pocket X/Y, seat Z, shear, target layer/Z; envelope-check; an embedded live preview of the planned insert motion (redraws on every keystroke, even out-of-envelope, so the operator can see why); "Animate…" opens the separate play/scrub popup (C16); **Save `<stem>.magnet.gcode`** and load it. |
| `magnet_embed/ui/settings_dialog.py` | "Settings" dialog — edit `printer.port`/`dispenser.port`/`magnet_tool_offset` from the panel, writes `config.local.yaml`. |
| `magnet_embed/ui/zcal_dialog.py` | "Z Calibrate…" dialog — guided paper-test Z-offset workflow: home + travel to `zcal.{x,y,start_z}`, fine nudge buttons, Save applies the accumulated nudge to the trusted `config.zcal.probe_z_offset` (`Controller.save_z_offset`), never a value read back from the printer. **Untested on real hardware** — see Known Technical Debt. |
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
- `Controller._printer_lock` (a `threading.Lock`) guards every `printer.command()`/
  `query_state()` call that could otherwise run concurrently with another one.
  `jog`/`extrude`/`send_command` stay idle-only (`self.running or self._busy`
  guard) and never touch the lock — nothing else can be running while they do.
  `home`/`level_bed`/`start_z_calibration` (C27) are also idle-only, but now
  run on a background thread (`_run_offline`) that *does* take the lock for
  its whole duration, so the Tk main loop stays responsive during a `G28`/`G29`
  that can take tens of seconds to a couple of minutes; `self._busy` is true
  for that whole span and gates every other idle-only action, including a
  second call to any of the three.
  `set_temp`/`refresh_state` are the two actions allowed to run *during* a
  print (and while a background one-off command is in flight) — they take the
  lock with a short bounded wait (`_LOCK_WAIT_S = 0.3` s, C27) rather than
  blocking indefinitely, so they can't relocate the same "Tk main loop frozen"
  problem C27 fixed onto themselves; failing to acquire it just skips that
  call (a log line for `set_temp`, silently for the timer-driven
  `refresh_state`). `GcodeRunner.run()` (constructed with the same lock in
  `start_run()`) takes it around each streamed line's send+`ok`, so a normal
  print and `set_temp`/`refresh_state` can't interleave on the shared serial
  connection either. `set_temp` additionally checks `Controller._in_insert`
  and refuses while `sequences.insert_magnet` is driving the printer directly
  (unlocked, on the worker thread) — the sequence owns the heaters during the
  pause (Dev Rule 6). `Controller.cancel()` (C27) spawns its own
  `_safe_cancel_retreat` thread that waits for the worker to stop before
  taking the lock — see Key Conventions.

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
  `M0`/`M1`/`M25`/`M600`/`M601` lines are skipped (`pauses_skipped`), never forwarded.
- `pause()`, `resume()`, `cancel()` — thread-safe.
- **C29 (opt-in).** `_transmit(raw, bare)` dispatches to plain `send_line`+`wait_ok`
  (today's default) or, with `config.gcode.use_line_numbers`, `_send_numbered`
  → `_send_and_resolve` (`N<n> ...*<checksum>`, `gcode.util.build_numbered_line`),
  which replays a `_RESEND_BUFFER = 64`-line buffer on `ResendRequested`
  instead of propagating it — recursive, one lock acquisition per top-level
  call (the lock isn't reentrant). `M110 N0` is sent once before streaming
  starts to reset the firmware's counter. With `config.gcode.
  resend_leveling_after_home`, `M420 S1` is re-sent right after any streamed
  `G28`.
- Side effects: reads the G-code file, writes to the printer link, appends to the run log.
- Exceptions: `AckTimeout`, `SentinelNotFound` (if `require_sentinel` and EOF reached first), `SentinelParseError`, `ResendRequested` (fatal only if a resend can't be serviced — unrecoverable without numbering, or if the requested line is no longer buffered).

### `gcode/postprocess.py`
- `inject_sentinel(in_path, out_path, *, layer: int | None, z_mm: float | None,
  pocket_xy: tuple[float, float], seat_z: float, shear: str, emit_pause: bool = False) -> int`
  — inserts `;MAGNET_INSERT X<px> Y<py> Z<seat_z> S<shear>` at the chosen layer and
  returns the sentinel's line number. `emit_pause` also writes a real `M0` just
  before it (so microSD prints pause too). Coordinates are in bed space.
- Understands Cura / Creality Print (`;LAYER:<n>`) and PrusaSlicer (`;LAYER_CHANGE` + `;Z:<h>`) markers.
- CLI: `python -m magnet_embed.gcode.postprocess <file> (--layer N | --z H) --xy PX PY --seat-z SZ --shear +X|-X|+Y|-Y [--pause] [-o OUT]`.
- Or use the panel's **Plan magnet insert…** dialog (`ui/plan_dialog.py`).

### `ui/settings_dialog.py`
- `SettingsDialog` + pure helper `build_updates`. Edits `printer.port`,
  `dispenser.port`, `magnet_tool_offset.{x,y,z}` and writes them via
  `config.save_local_override` (deep-merged onto `config.local.yaml`, the
  committed `config.yaml` is never touched). Reloads `controller.config` on
  save so an offset change applies to the very next insert immediately; a
  port change needs an app restart (the link objects are already constructed
  with the old port — see `entry.build_links`). Opened from the panel's
  "Settings…" button.

### `ui/plan_dialog.py`
- `PlanInsertDialog` + pure helpers `resolve_target_z`, `magnet_output_path`,
  `save_magnet_gcode`, `envelope_report`. Enter pocket X/Y, seat Z, shear, and a
  target (layer index or Z height); live envelope check; **Save** writes
  `<stem>.magnet.gcode` and loads it as the active file. Seat-Z defaults to the
  chosen insert layer's own height (C31) — previously defaulted to the file's
  overall top independent of the insert layer, which put the default seat
  above where the insert actually happens whenever the part had more layers
  above it.
- **Embedded insert-motion preview (C22).** `_redraw_embedded_preview`, called
  from `_check()` on every keystroke — an X-Y + X-Z pair (`viz.toolpath_fig
  .draw_layer_xy`/`draw_side_xz`/`draw_insert_overlay`) showing the
  phase-coloured planned nozzle path, the dashed pole path, and the pocket
  marker, built from the same `sequences.geometry.plan_insert_moves` output
  `insert_magnet` actually drives (via `plan_for`) — can't drift from the real
  run. Drawn even when out-of-envelope so the operator can see why. **"Animate…"**
  (renamed from "Preview" in C22) still opens the separate C16 popup for the
  full play/scrub/3D experience — the embed is a live static complement, not a
  replacement.

### `sequences/geometry.py`
- `compute_targets(mi, config, saved) -> Targets` (`approach_xy`, `press_z`,
  `shear_xy`, `safe_z`), `plan_insert_moves(mi, config, saved) -> list[InsertMove]`
  (nozzle-tip waypoints, phase-tagged), `check_envelope(mi, config, saved,
  toolpath=None) -> list[str]`, `part_footprint(toolpath, margin_mm)`,
  `pole_point(nozzle, config) -> Point`.
- Pure. `insert_magnet` builds its targets here; the C16 preview and C17 dialog draw
  and envelope-check the *same* function output — the preview cannot drift from the run.
- **`check_envelope` is the damage guard (C25, Dev Rules 7 + 12).** One
  plain-language reason per problem, empty means OK. In order: (1) the pocket
  itself is on the bed (a pocket off the bed with a nozzle target on it was
  previously accepted); (2) approach/shear XY and safe Z inside `machine.*`;
  (3) `press_z < 0` → "nozzle would hit the build plate"; (4) with a
  `toolpath`, `_part_collisions`: the part is printed up to `saved.z` when the
  sentinel fires, so if `press_z < saved.z + collision.nozzle_clearance_mm`
  and the nozzle XY at PRESS or at any of 10 sampled points along SHEAR lies
  inside `_printed_footprint` (C30 — a bbox grown by `collision.
  footprint_margin_mm`, but built from only the segments in layers `0 ..
  layer_for_z(saved.z)` — the layers actually printed at insert time, not
  the whole file) → "nozzle would enter the printed part during PRESS/SHEAR
  …" with the numbers and the fix (pocket within the offset of a part edge,
  or change the offset). `_printed_footprint` is always a subset of the
  older whole-file `part_footprint` (still exported, now only its
  fallback for the edge case of no extruding segments in range), so C30 can
  only *stop* flagging geometry that doesn't physically exist yet — it can't
  weaken protection for anything actually printed. Still a bounding box
  (per printed range, not per exact shape) — an L-shaped *printed*
  cross-section is still its enclosing rectangle; true concave/polygon
  occupancy is a further TODO. Without a toolpath only (1)–(3) run. The pole
  tip touching the pocket is the intended contact and is never flagged.

### `sequences/insert_magnet.py`
- `insert_magnet(printer: PrinterLink, dispenser: DispenserLink | None, mi: MagnetInsert,
  config: dict, prompt: Callable[[str], str], *, toolpath: Toolpath | None = None,
  on_phase: Callable[[str, tuple[float, float, float] | None], None] | None = None) -> None`
  — `mi` carries the parsed sentinel fields; `prompt("dispense")` returns
  `"ready" | "abort"` (only used when `dispenser` is `None`), `prompt("confirm")`
  returns `"success" | "retry" | "abort"`; `toolpath` is the parsed file being
  printed (`Controller` passes its cached one, `entry.run_headless` parses it
  best-effort) and enables the nozzle-vs-part collision guard.
- `on_phase` (C26), if given, is called once per phase — `PARK`, `DISPENSE`,
  `APPROACH`, `PRESS`, `SHEAR`, `LIFT`, `CONFIRM`, `RESUME` — right before that
  phase's motion is sent, with the exact nozzle-tip target it's about to move
  to (`None` for the two non-motion phases). Re-fires every retry loop
  iteration except `PARK`, which only runs once. Lets `Controller` drive the
  panel's live view during the insert instead of it freezing at the sentinel.
- Targets from `geometry.compute_targets`; damage guard from
  `geometry.check_envelope(..., toolpath)` (raises `OutOfEnvelopeError` if
  non-empty — before any line is sent). Runs the state machine in
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
- Actions: `connect` (idempotent, C28 — a no-op while already connected and
  not `estopped`), `disconnect` (C28 — idempotent, refused while
  `running`/`busy`), `load_gcode`, `jog`, `home`, `level_bed` (`G28`→`G29`→
  `M420 S1`→`M500`), `send_command` (raw G-code line), `extrude` (mm+feed,
  negative = retract), `start_z_calibration` (`G28` then travel to
  `zcal.{x,y,start_z}`), `nudge_z` (fine relative Z move at `zcal.feed`),
  `save_z_offset` (applies the accumulated nudge to `config.zcal.probe_z_offset`,
  sends `M851`+`M500`, persists via `save_local_override` and updates
  `self.config` in place - same apply-immediately pattern as the Settings
  dialog's magnet offset) — all no-ops while a run is active, and all now
  surface a `PrinterError`/`AckTimeout`/`ResendRequested` as an `error` event
  instead of raising — plus `start_run`, `pause`, `resume`, `cancel`,
  `answer_prompt`, and **`emergency_stop()`** (C25): allowed at *any* time —
  cancels the runner, injects an `"abort"` answer if the worker is blocked on
  an operator prompt (`_prompt_pending`), then writes `M112` straight to the
  link with `send_line` — **no idle guard, no `_printer_lock`, no `wait_ok`**
  (the worker may hold the lock inside `wait_ok` for up to `ack_timeout_s`;
  an e-stop cannot wait for that; any `ok` the board returns for `M112` may
  be eaten by the worker's in-flight `wait_ok`, harmless since the run is
  being cancelled). Sets `estopped` (property) and emits an `error` telling
  the operator to power-cycle / `M999` and Connect again; `connect()` clears
  it; `refresh_state` is a no-op while `estopped` so the 2 s idle poll doesn't
  spam errors against a halted board. A failure to send is reported as an
  `error` ("use the printer's power switch"), never raised out of a button.
  Marlin honours `M112` ahead of the queue only with `EMERGENCY_PARSER`
  compiled in — unverified on the stock V3 SE firmware; without it the stop
  still executes as the next queued command. `level_bed` blocks the caller for the whole probe (can be a
  couple of minutes) — same accepted trade-off as `home`, just longer;
  `wait_ok` already tolerates it via Marlin's `busy:` keepalive
  (`DEFAULT_KEEPALIVE_INTERVAL 2` in the stock firmware, well under
  `ack_timeout_s`).
- `set_temp(which, value)` and `refresh_state()` are the exception to "idle
  only": neither touches motion (`M104`/`M140`/`M105`/`M400`/`M114`), so both
  are allowed **during a normal print** (locked against the streaming loop —
  see Threading model) but refuse (`set_temp`: log line; `refresh_state`:
  silent no-op) while the magnet-insert sequence owns the printer (`_in_insert`).
  `set_temp`'s `value` is range-checked against
  `config['temps'][{nozzle,bed}_{min,max}_c]` first — out of range or a link
  error both emit an `error` event, nothing is sent.
- Properties: `connected`, `progress` → `(current_line, total_lines)`, `progress_point`
  → the nozzle tip's `(x, y, z)` implied by that line progress against the cached
  `toolpath` (`None` if no toolpath), `current_line_text` → the raw source line at
  that progress (`""` if none), `toolpath`/`gcode_lines` (cached by `load_gcode()`,
  best-effort), `link_summary` → `"simulator"` / `"printer COM3"` / `"printer
  COM3 + dispenser COM4"` (whether `printer`/`dispenser` have a real `.port`),
  `in_insert` (C26) → whether `insert_magnet` currently owns the printer,
  `busy` (C27) → whether a background one-off command (`_run_offline`) is in
  flight.
- `_on_insert_phase(phase, position)` (C26) — the `on_phase` callback passed
  into `insert_magnet`; emits a `"phase"` event (`{"phase": ..., "position":
  ...}`) so the panel's live view can track the actual insert motion instead
  of the frozen line-progress position.
- Event kinds: `log`, `state` (a `PrinterState`), `prompt` (`"dispense"`/`"confirm"`),
  `done`, `error`, `phase` (`{"phase": str, "position": (x,y,z) | None}`, C26).
- `_run_offline(fn)` (C27) — runs `fn` (which does its printer calls inside
  `with self._printer_lock:`) on a daemon thread, `self._busy = True` for the
  duration; `home()`/`level_bed()`/`start_z_calibration()` are built on it so
  none of the three blocks the Tk main loop. `cancel()` similarly spawns a
  `_safe_cancel_retreat` thread (waits for the worker to actually stop, then
  retract/lift/park/heaters-off — see Key Conventions and Known Technical
  Debt). Every idle-only action's guard is `if self.running or self._busy:`.

### `ui/panel.py` — `ControlPanel` + `run_gui(controller)`
- Thin Tkinter view over a `Controller`. `self.btn_connect` (C28) is a
  Connect ↔ Disconnect toggle — `_toggle_connect` dispatches on
  `Controller.connected`, and its label/enabled-state are refreshed every
  `_refresh_buttons()` poll (disabled while `busy`, same as the other
  idle-only controls). Load G-code, run/**Pause↔Resume** (C31 — one
  `self.btn_pause` toggle, `_toggle_pause` dispatches on `Controller.paused`,
  same pattern as Connect/Disconnect; was two separate buttons)/cancel,
  a red **EMERGENCY STOP** button at the top right (`self.btn_estop`, a plain
  `tk.Button` because the Windows ttk theme ignores background colours;
  always enabled, no confirm dialog, calls `Controller.emergency_stop`),
  a run-progress bar, jog (0.1/1/10 mm, bigger click targets since C31, plus
  arrow-key/Page-Up-Down jog — `_bind_jog_keys`, bound on the toplevel and
  ignored while a text-entry widget has focus or the panel is busy/running)
  + home + "Level Bed…" + "Z Calibrate…" (confirm dialogs first — both move
  the toolhead) + raw G-code entry + extrude/retract **idle only**, "Plan
  magnet insert…", read-only log, live position/temp line, an embedded
  **live-print view**. Auto-refreshes state every `ui.idle_poll_s` while
  connected + idle. `_show_prompt` opens a modal **Success / Retry / Abort**
  (or **Ready / Abort**) dialog that calls `controller.answer_prompt`. Drains
  `poll_events()` every 120 ms; a `"done"` event logs a human-readable
  "run finished: N/M lines sent, K magnet insert(s)" line (C31 — was a raw
  dict dump).
- **Two-column layout, opens maximized (C24).** `_build` puts the top
  bar/files/run/progress rows across the full width, then `_build_left`
  (jog/home, temperature, filament) and `_build_right` (live-print view,
  send-G-code, state line, log) sit side by side — `self.body`'s column 1
  (right) carries the grid weight, so it consumes whatever extra width a
  maximized window grants. `run_gui()` calls `root.state("zoomed")` to open
  maximized by default (Windows; falls back to a fixed `1200x820` geometry
  with a caught `tk.TclError` elsewhere, since `"zoomed"` isn't a universal
  Tk state).
- **Scrollable, as a fallback (C22/C24).** `_build_scroll_container` wraps
  everything in a `Canvas` + `Scrollbar` (content built onto `self.body`, not
  `self` directly) for a screen too small to fit everything even maximized;
  it scrolls instead of clipping the bottom rows off-window. Mouse-wheel
  binding is scoped to `<Enter>`/`<Leave>` on the canvas so it doesn't hijack
  scrolling inside a dialog's own widgets. C24: the canvas's `<Configure>`
  handler now stretches the `self.body` window item to **at least** the
  canvas's own visible height (`max(event.height, body.winfo_reqheight())`) —
  previously only width was stretched, so a maximized window's extra
  vertical space just sat blank below a short, un-stretched body instead of
  reaching the weighted rows (the live view, the log); now those rows
  actually grow to fill it, and the fallback to natural height (→ scrolling)
  still applies whenever content genuinely doesn't fit.
- **Mode/port label (C22).** `self.target_lbl` next to the connection status
  shows `controller.link_summary` (`"simulator"` / `"printer COM3"` / …) so
  "connected" is never ambiguous about *what* — the status text itself was
  already correct (`not connected` until `Controller.connect()` actually
  succeeds), the real gap was no visibility into which target it applied to.
- **Live-print view** (`_sync_live_view`, C20/C22/C23/C24) — two
  `FigureCanvasTkAgg` widgets side by side in the right column, always both
  visible (no 2D/3D toggle, removed in C23): `live2d_*` shows the active
  layer's 2D toolpath plus a marker at `controller.progress_point`; `live3d_*`
  shows either the whole bed or just the part isometrically
  (`viz.toolpath_fig.draw_live_3d`/`update_live_3d`, per `self.live3d_global`)
  with a path that **grows progressively** as the nozzle actually passes
  through it (`progressive_path_3d`, not the whole part drawn upfront) and
  tight equal-mm-per-axis scaling (`ax.set_box_aspect` + explicit
  `set_xlim`/`set_ylim`/`set_zlim`, so a wide flat part looks wide and flat —
  not stretched to a cube, and not swamped by matplotlib's default autoscale
  margin either, which is what caused the "extreme Z gaps" C24 fixed). A
  **"Global bed" / "Local part"** button (`_toggle_bed_view`) next to the 3D
  view's header swaps `live3d_global` and resets only `_live_art3d` — Global
  spans the real bed with the plate outline drawn (real scale, real context);
  Local crops tight to the part's own bbox with no bed outline (fills the
  view — a short/flat part is otherwise "hardly visible" against a 220 mm
  bed, per C24 driving feedback; confirmed via the introspection script that
  Local's box-aspect Z ratio is ~2.7× larger than Global's for the sample
  file). **Defaults to Local (C31)** — `self.live3d_global = False` and the
  button's initial label ("Local part") match; Global is one click away. A
  label under both canvases shows `controller.current_line_text` —
  "what the current step looks like" as text, not just a dot on the plot. The
  2D layer only redraws when the active layer changes; the 3D path/marker
  update via cheap `set_data`/`set_3d_properties` calls, not a full redraw —
  both cheap enough to run often. Throttled off the existing 120 ms tick via
  `ui.live_view_poll_s` (default **0.15 s** — lowered from 1.0 s in C22 once
  driving feedback called the motion "not smooth"). **3D throttled further
  still (C31)** — `ui.live3d_poll_s` (default **0.3 s**, ~2× the 2D rate)
  gates `_live3d_calls % self._live3d_every == 0` around the 3D
  update+`draw_idle()` only; the 2D marker still updates every tick. A full
  `Axes3D` redraw costs more than a `Line2D` `set_data` call, and this was
  one of the two measured contributors to the owner's "system feels slow"
  report (the other — the Animate popup's 40 ms tick running even while
  paused — is fixed in `viz/preview.py`, see its own entry). Static (current
  layer, no marker/path) once a file loads; tracks line progress once a run
  starts and freezes at the final position when it ends. No extra printer
  traffic — position comes from `Toolpath.progress_position`, not a polled
  `M114`.
- **Insert-phase override (C26).** While `controller.in_insert` and a
  `"phase"` event has arrived, the 2D marker (`tf.update_live_marker`) and 3D
  marker (`tf.update_live_3d_marker`, marker-only, doesn't touch the growing
  path) move to that phase's waypoint instead of `progress_position`, the 2D
  layer and 3D path stay frozen at the sentinel, and the "current step" label
  reads `"magnet insert in progress - phase: <PHASE>"`. Reverts to
  line-progress-driven the moment `in_insert` goes false — no dependency on a
  specific completion event.
- **"Z Calibrate…"** (`ui/zcal_dialog.ZCalDialog`, C21) — opens next to "Level
  Bed…"; idle-only. See its own module-table row and Known Technical Debt for
  the config-is-the-trusted-offset design and the real-hardware caveat. Both
  calibration buttons now carry a one-line caption (C22) distinguishing the
  ABL mesh probe from the single nozzle-to-bed offset — driving feedback
  flagged that two calibration buttons with no explanation looked redundant.
- Temperature panel is *not* idle-gated (`set_temp` works mid-print, see `app.py`):
  each of the nozzle/bed rows shows the allowed range from
  `config['temps'][{nozzle,bed}_{min,max}_c]` and a live `now: A/B°C` label
  (actual/target) updated from every `state` event — not just the polled-while-idle
  ones, so it also refreshes right after a `set_temp` call made during a print.
  Note: with no sentinel and no explicit `set_temp`/jog/home/extrude/connect call,
  nothing emits a `state` event mid-stream, so the `now:` label can go briefly
  stale during a long ordinary print — seen the real value again on your next Set.

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
- **Firmware-pause codes are dropped, not streamed.** `GcodeRunner` skips any
  `M0` / `M1` / `M25` / `M600` / `M601` line (`pauses_skipped` counts them) — the
  host owns the pause and the insert sequence does the parking. So a
  `*.magnet.gcode` saved with the dialog's "also write a real `M0`" option still
  streams cleanly through the host *and* pauses when printed straight from microSD.
- **Magnet-tool offset.** `magnet_tool_offset: {x, y, z}` is **(holding-pole tip) −
  (nozzle tip)**, measured empirically with signs. `+z` means the pole tip sits above
  the nozzle tip. `insert_magnet` drives the carriage to `pocket_xy − (offset.x,
  offset.y)` and presses the nozzle down to `seat_z − offset.z` (so the pole tip lands
  at `seat_z`). The offset shrinks the reachable area and can make a low pocket
  unreachable (`seat_z − offset.z < 0`) — the host checks every target in-envelope and
  **aborts the sequence with the print still paused** if not.
- **Pole above the nozzle means the nozzle goes below the seat.** With
  `offset.z > 0` the nozzle presses to `seat_z − offset.z`, *below* the printed
  top, `offset.xy` away from the pocket — so the pocket must sit within the
  X/Y offset of a part edge or the nozzle lands inside the part. The C25 guard
  (`geometry.check_envelope` with the toolpath) refuses that case in the Plan
  dialog, the preview and the run alike; `config.collision.*` sets the
  clearance and footprint margin.
- **Z-probe offset is trusted from config, not read back from the printer.**
  `config.zcal.probe_z_offset` — same pattern as `magnet_tool_offset`: measure
  the real value once (send a bare `M851` from a terminal), put it in
  `config.local.yaml`, and every "Z Calibrate…" save adjusts *that* number by
  the accumulated nudge, then pushes the result with `M851 Z<new>` + `M500`.
  Chosen over parsing the firmware's `M851` report because that report's exact
  text format for this printer's firmware fork was never verified — see Known
  Technical Debt.
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
- **Safe-cancel retreat (C27).** `Controller.cancel()` stops streaming, then —
  once the worker has actually stopped (bounded `join`, never while an insert
  still owns the printer) — retracts, lifts, parks at `park.{x,y}`, and (if
  `config.cancel.heaters_off`, default `true`) turns both heaters off. Skipped
  entirely after an e-stop (`estopped`) or if the worker is still finishing
  something (e.g. an insert's pending operator prompt) — logs that it was
  skipped rather than racing that code's own printer calls.

---

## Data Files

| File | Tracked? | Notes |
|------|----------|-------|
| `.CLAUDE/*.md`, `project/*.md`, `docs/*.md`, `README.md`, `TODO.md` | yes | Project docs. `CLAUDE-COMMON.md` is shared — never edit here. `HOW_IT_WORKS.md` = plain-language guide; `RESEARCH.md` = prior-art survey; `BUILD_PLAN.md` = chunk plan; `docs/INVENTION_DISCLOSURE_DRAFT.md` = patent-form draft; `docs/PRIOR_ART_PATENT_SEARCH.md` = informal patent search (2026-09-18) behind its Q5/Q19. |
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
- [ ] Before the first real "Z Calibrate…" run: read the printer's actual `M851`
      value from a terminal and set `zcal.probe_z_offset` in `config.local.yaml`
      to match (see Known Technical Debt — the app never reads it back itself)

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

- **No hardware validation of the magnet flow yet.** The whole stack is proven
  against `SimPrinter` / `SimDispenser` (225 tests); only the printer *serial
  link* and a plain streamed print have run on the real machine (COM3). The
  first magnet-flow bench session may surface firmware-serial quirks (the
  Ender-3 V3 SE has known OctoPrint friction) and mechanism issues. Treat it as
  debugging, not production.
- ~~Nozzle-vs-part collision is not checked~~ — **fixed in C25**
  (`geometry.check_envelope(..., toolpath)`, see Key Modules). ~~The
  footprint counted layers that haven't been printed yet~~ — **narrowed in
  C30** (`geometry._printed_footprint`, restricted to layers `0 ..
  layer_for_z(saved.z)`). Remaining limits of the guard: the footprint is
  still a **bounding box** of the printed-so-far layers, not the exact
  shape (an L-shaped *printed* cross-section is treated as its enclosing
  rectangle — conservative, may still refuse a legal pocket in a concave
  part); the **applicator body** itself is
  not modelled (only the nozzle tip is tested — measure the add-on's lowest
  point vs. the nozzle and, if it hangs lower, fold that into
  `collision.nozzle_clearance_mm`); `saved.z` is taken as the printed top
  (true at a layer start, which is where the sentinel sits). With a
  pole-above-nozzle offset the guard will, correctly, refuse any pocket more
  than `|offset.x|`/`|offset.y|` from a part edge — the deployable-pole /
  pocket-near-edge design decision is still open (`project/PROJECT_PLAN.md`
  §6).
- ~~No emergency stop~~ — **fixed in C25** (`Controller.emergency_stop`, red
  panel button). Unverified on hardware: whether the stock V3 SE firmware has
  `EMERGENCY_PARSER` (`M112` honoured mid-command) — bench-test the button
  with a long move in flight before relying on it.
- ~~No safe cancel~~ — **fixed in C27**. `Controller.cancel()` now spawns a
  background `_safe_cancel_retreat` that waits for the worker to actually
  stop, then retracts, lifts, parks at `park.{x,y}`, and (if
  `config.cancel.heaters_off`, default `true`) sends `M104 S0`/`M140 S0`.
  Skips the retreat if the worker is still alive after a bounded join (e.g.
  cancel pressed mid-insert, while the operator prompt is still pending) —
  logs that it was skipped rather than racing `insert_magnet`'s own printer
  calls, and tells the operator to use EMERGENCY STOP if it's urgent.
- ~~Home / Level Bed / Z Calibrate block the Tk main thread~~ — **fixed in
  C27**. All three now run on a background thread (`Controller._run_offline`,
  under `_printer_lock`) instead of blocking the caller; a new `busy`
  property/`_busy` flag guards every other idle-only action (and a second
  call to any of the three) while one is in flight, the same way `running`
  already did. `nudge_z`/`save_z_offset` stay synchronous on purpose — single
  fast commands, not the reported freeze. Because a background action can now
  hold `_printer_lock` for a long time, `set_temp`/`refresh_state` switched
  from an unbounded `with self._printer_lock:` to a short bounded wait
  (`_LOCK_WAIT_S = 0.3` s) so they can't relocate the same freeze onto
  themselves — long enough to ride out the streaming loop's normal brief
  per-line hold, short enough to never be perceptible.
- ~~`Controller.connect` is not idempotent and there is no Disconnect~~ —
  **fixed in C28**. `connect()` is now a no-op (logs "already connected")
  when already connected and not `estopped` — the `estopped` exception
  matters because `emergency_stop()` never flips `_connected` off, so
  Connect must still work there to clear `estopped`, without re-opening the
  port. New `disconnect()` (idempotent, refused while `running`/`busy`)
  closes the printer and dispenser links independently (one failing doesn't
  block the other) and clears `_connected`. `ui/panel.py`'s single Connect
  button is now a Connect ↔ Disconnect toggle (`_toggle_connect`, label
  refreshed every poll from `Controller.connected`).
- ~~The insert sequence is invisible while it runs~~ — **fixed in C26**
  (`insert_magnet(..., on_phase=)`, `Controller.in_insert`/`_on_insert_phase`,
  `ui/panel.py._sync_live_view`, see Key Modules). Still open: no log line per
  phase (only the live-view label updates) and no planned-path *overlay* drawn
  on the 2D axes during the insert (the 2D layer just freezes and the marker
  jumps to each phase's waypoint) — a nice-to-have, not a correctness gap.
- ~~Plain-line streaming has no resend recovery~~ — **fixed in C29, opt-in
  and unverified on hardware.** `config.gcode.use_line_numbers` (default
  `false`, preserving today's bench-tested plain-line behavior) makes
  `GcodeRunner` send `N<n> ...*<checksum>` lines and replay a small buffer
  (`_RESEND_BUFFER = 64`) of recently sent lines on a `Resend:` instead of
  ending the run; a resend for a line the buffer no longer holds is still
  fatal, same as before. `printer_sim.py`/`printer_serial.py` both strip the
  wrapper before parsing (`gcode.util.strip_line_number`) so either format
  works regardless of the flag. Also opt-in: `config.gcode.
  resend_leveling_after_home` re-sends `M420 S1` right after any streamed
  `G28` (see the first-layer-quality debt item above — this is the automated
  fix that item flagged as "not built"). **Bench-test both flags before
  enabling them for a real print** — nothing about the real V3 SE firmware's
  checksum/resend behavior has been verified, same caveat as Z-cal and
  `EMERGENCY_PARSER`.
- **Tool offset / press depth / shear params in `config.yaml` are guesses.** They must
  be measured on the real machine (`config.local.yaml`) — see `PROJECT_PLAN.md` §8.
- **`dispenser_fw/` (the Arduino sketch) does not exist yet.** `SerialDispenser`
  assumes the `PING`/`DISPENSE`/… protocol; the sketch must implement it. Until then
  every real run is `--printer` (or `--hardware` with the Uno absent) and the insert
  falls back to the operator "Load a magnet" prompt.
- **`matplotlib` added for `viz/`; `uv` migration still pending** (Dev Rule 9 — flag
  when touching packaging).
- **The preview's `saved` state is approximated** (`toolpath_fig.state_at_z`) — the
  real run uses the true position at the sentinel. Fine for a sanity check; the
  envelope numbers can differ slightly from the live run if the print is far from
  the pocket XY when it pauses.
- ~~No periodic temp polling during an active print~~ — fixed: `refresh_state()`
  now runs on the normal `ui.idle_poll_s` timer during a run too (locked, and
  blocked only during an active insert), so the panel's `now:` labels stay live
  throughout an ordinary print, not just right after an explicit action.
- **`temps.nozzle_max_c` (260°C) / `bed_max_c` (100°C) in `config.yaml` are
  conservative guesses**, not the Ender-3 V3 SE's real firmware `MAXTEMP`/bed
  ceiling — they only gate the host-side `set_temp` UI, they are not read from
  the printer. Raise them in `config.local.yaml` if your hotend/bed is rated higher.
- **First-layer quality issue, root-caused 2026-09-15 (not a bug in this repo):**
  the stock Ender-3 V3 SE firmware ships with `RESTORE_LEVELING_AFTER_G28`
  disabled ([`CrealityOfficial/Ender-3V3-SE` `Configuration.h`
  line 1521](https://github.com/CrealityOfficial/Ender-3V3-SE/blob/main/Marlin/Configuration.h)),
  so any `G28` turns bed-mesh compensation back off; the Creality Print slicer
  profile used for `Cube_PETG_7m59s.gcode` never sends `M420 S1` to re-enable
  it, so that print ran with an uncorrected mesh the whole time. The new
  **Level Bed…** panel button (`Controller.level_bed`) probes + enables + saves
  a mesh on demand, but that enabled state does **not** survive the print's own
  `G28` unless something re-sends `M420 S1` right after it — either add that
  line to the slicer's start G-code, or turn on `config.gcode.
  resend_leveling_after_home` (**built in C29**, opt-in, unverified on real
  hardware — see Known Technical Debt above) to have `GcodeRunner` do it
  automatically.
- **The "Z Calibrate…" workflow (C21, `ui/zcal_dialog.py` / `Controller.
  start_z_calibration`/`nudge_z`/`save_z_offset`) is entirely unverified on
  real hardware** — built and tested only against `SimPrinter`. Two specific
  unknowns: (1) whether the stock V3 SE firmware fork accepts `M851 Z<value>`
  + `M500` the way stock Marlin does — not confirmed; (2) `config.zcal.
  probe_z_offset` is trusted from config, never read back from the printer
  (a deliberate choice — the real `M851` report text format for this firmware
  fork was not available to verify a parser against, and trusting an
  unverified parse of a bed-proximity value was judged riskier than trusting
  a config value the operator measured once). Before the first real
  calibration: read the printer's actual `M851` value from a terminal and set
  `zcal.probe_z_offset` in `config.local.yaml` to match, start with a large
  step (0.5 mm), and watch the machine closely — see the Pre-hardware
  checklist item added for this.
- **A real mid-session disconnect isn't reflected in the panel's status
  label.** `Controller._connected` is set `True` in `connect()` and never
  un-set — a physically unplugged USB cable or a dead serial port surfaces
  only as an `error` event on the next command that tries to use it (jog,
  `refresh_state`, …), not as the status flipping back to "not connected".
  Flagged during the C22 GUI pass; not fixed because there's no printer on
  hand right now to validate real failure behaviour against (an `AckTimeout`
  doesn't always mean "disconnected" — it can just mean a slow response — so
  guessing the right signal without hardware risked a worse false-positive).
  Revisit once the applicator/bench work resumes.

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
12. **The insert must pass the damage guard after the tool offset is applied** —
    `geometry.check_envelope`: pocket on the bed, nozzle targets in range, no
    press into the plate, no press/shear into the printed part. The sequence
    checks and aborts (print stays paused) rather than commanding the move;
    the Plan dialog and preview run the same check. (project)
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
