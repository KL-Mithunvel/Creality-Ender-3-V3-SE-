# Proto Execution Plan — printer control → slicing → magnet

A from-scratch, **hardware-first** plan. Each phase is validated against the real
Ender-3 V3 SE before the next starts. Supersedes `project/BUILD_PLAN.md` for all
forward work; BUILD_PLAN's C1–C8 history stays as-is.

| | |
|--|--|
| Owner | kl mithunvel |
| Created | 2026-09-09 |
| Supersedes | `project/BUILD_PLAN.md` Phase 1.5 (C9–C12 dropped) |
| Overall roadmap | `project/PROJECT_PLAN.md` |
| Architecture / rules | `.CLAUDE/CLAUDE.md` |

---

## Decisions (owner, 2026-09-09)

| Question | Decision | Consequence |
|----------|----------|-------------|
| Build from Printrun/Pronterface code? | **No.** | Printrun is GPLv3, this repo is MIT — copying its code forces a relicense. Read it for *approach* only. |
| Slicer | **Creality Print 7 CLI** (`CrealityPrint.exe --slice …`). | Already installed at `C:\Program Files\Creality\Creality Print 7.0\`. Orca-lineage CLI. **Fallback: OrcaSlicer** — same flags, profiles transfer — if the CP CLI proves unstable (known 3MF-slice crash upstream). |
| `proto_run.py` form | **CLI + GUI from the start.** | `proto_run.py` (repo root) probes hardware and dispatches; `--gui` opens the Tkinter panel. Both drive the same headless controller. |
| Codebase | **Fresh minimal `proto/` package.** | Port `SerialPrinter` (+ `_marlin_rx`), `GcodeRunner`, `PrinterState`, the exception types, and **their tests** — coverage is ported, not lost. `magnet_embed/` stays untouched in the tree as the Phase-P3 source. |

### Scope guard

- No `printrun` / `printcore` dependency, no copied Pronterface code.
- Slicing is a **subprocess call** to an installed slicer — we never bundle or link one.
- No firmware reflash; stock Creality firmware, plain-line streaming (as today).
- Magnet-specific code (insert sequence, dispenser, sentinel) is **out of scope
  until P3** and is not ported early — it already exists in `magnet_embed/`.

---

## Target pipeline

```
STL ──[P2: CrealityPrint.exe --slice]──► G-code ──[P3: inject pause / magnet marker]──► [P1: GcodeStreamer]──► Ender-3 V3 SE
       (external, subprocess)                       (postprocess, ported later)          (our MIT streaming loop)
```

P1 builds the right-hand box on real hardware. P2 adds the left box. P3 adds the middle.

---

## New package layout (`proto/`)

```
proto/
  __init__.py
  config.py         load_config() — ports, baud, timeouts, slicer exe path; config.yaml + config.local.yaml
  config.yaml       committed defaults (COM3 / 115200 / CrealityPrint.exe path)
  errors.py         PrinterConnectionError, AckTimeout, PrinterError, ResendRequested, StreamError, SliceError
  state.py          PrinterState dataclass  (ported)
  marlin.py         classify() + parse_temps() + parse_position()  (ported from links/_marlin_rx.py)
  printer.py        SerialPrinter  (ported from links/printer_serial.py; no dispenser concepts)
  streamer.py       GcodeStreamer  (ported from gcode/runner.py; sentinel detection removed for now)
  controls.py       jog(), home(), set_temp(), extrude(), send_command() — thin G-code builders + link calls
  controller.py     headless Controller — worker thread, event queue, idle polling  (slimmed from app.py)
  ui.py             Tkinter panel  (ported from ui/panel.py, minus the magnet prompt)
  slicer.py         [P2] slice(stl, profile, out_dir) -> gcode_path  via CrealityPrint.exe
proto_run.py        repo root — hardware probe + dispatch (--gui, --stream FILE, --slice STL, ...)
tests/
  test_proto_*.py   ported + new
```

`python -m pytest` stays green across the whole repo (old `magnet_embed` tests + new `proto` tests).

---

## Phases

### P0 — package skeleton + hardware probe  🟢

**Goal.** The `proto/` package exists with the ported streaming core and passes
tests. `proto_run.py --probe` says what's plugged in.

**Files:** everything under `proto/` except `slicer.py`, `ui.py` extras; `proto_run.py`
with `--probe` only; ported tests (`test_proto_marlin.py`, `test_proto_printer.py`,
`test_proto_streamer.py` — adapted from `test_serial_links.py` / `test_runner.py`
with the fake-serial transport).

**Acceptance**
- `python -m pytest` green (old + new).
- `python proto_run.py --probe` → prints `printer: COM3 OK  (Marlin …)` / `printer: COM3 FAIL (…)`
  and `dispenser: not checked` (Uno support is a stub until P3).
- `python proto_run.py --probe --uno` → also PINGs the Uno if a port is configured.
- No `magnet_embed` imports anywhere in `proto/`.

---

### P1 — basic printer control, on the bench  🟢

Each sub-step is verified **against the real printer**, not just the fake transport.

| Step | Goal | Acceptance |
|------|------|------------|
| **P1.1** | Stream an existing `.gcode` from `proto_run.py --stream FILE` — `ok` handshake, pause/resume/cancel | A real sliced file prints start to finish; Ctrl-C → clean cancel; pause holds position |
| **P1.2** | Manual control from the CLI: `home`, `jog X 10`, `temp nozzle 200`, raw line `send M114` | Each verified on the machine; jog respects `travel.feed`; no `G28` surprises |
| **P1.3** | GUI (`proto/ui.py`, `proto_run.py --gui`): connect, load+stream, jog/home/temps, raw command box, log, live position/temp line | Panel drives a real print; controls disabled while streaming |
| **P1.4** | Live idle polling (`M105`+`M114` every ~2 s while idle), extrude/retract buttons, run-progress bar (`line N / total`) | Readout tracks the machine; progress bar advances during a real print |

**Files:** `proto/streamer.py`, `proto/controls.py`, `proto/controller.py`,
`proto/ui.py`, `proto_run.py`. Config: `proto/config.yaml` gains `ui.idle_poll_s`.

---

### P2 — slicing (STL → G-code)  🟢

**Goal.** `proto_run.py --slice model.stl` produces a printable `.gcode` using
Creality Print's CLI, then can hand it straight to P1's streamer.

| Step | Goal |
|------|------|
| **P2.1** | `proto/slicer.py` — resolve `CrealityPrint.exe` (config `slicer.exe`), run `--slice` with a profile into a temp dir, return the `.gcode` path; raise `SliceError` with stderr on failure. Verify the exact CLI flags against CP 7 first (spike). |
| **P2.2** | Profile: export an Ender-3 V3 SE + <your filament> config/`.3mf` from the Creality Print GUI, commit it under `proto/profiles/`, document the export steps. |
| **P2.3** | `proto_run.py` flow: `--slice STL` → slice → print layer count / height / est. time → optional `--print` to stream it. STL thumbnail via the bundled `stl-thumb.exe` (optional, nice for the GUI). |
| **P2.4** | GUI: **Open STL → Slice → Print** buttons wired to the same path. |

**Risk / fallback.** Upstream reports the CP CLI can crash on some 3MF inputs. If we
hit that: switch `slicer.exe` to OrcaSlicer (identical `--slice` interface, and
Creality Print profiles import into Orca). `proto/slicer.py` stays the same shape.

**Acceptance**
- A known-good STL slices to G-code that prints correctly on the Ender-3.
- Slice failure surfaces a readable `SliceError`, no half-written output kept.

---

### P3 — pause & magnet embedding (revisit when the applicator exists)  🟢

Mostly *re-connecting* code that already exists in `magnet_embed/`.

| Step | Goal |
|------|------|
| **P3.1** | "Insert pause at layer N" — port `gcode/postprocess.py` marker injection into `proto/`. Support a plain `M0` / host-pause (non-magnet use) **and** the `;MAGNET_INSERT` sentinel. |
| **P3.2** | Re-attach the magnet insert sequence: bring `insert_magnet`, the dispenser link + sim, and the Uno protocol across from `magnet_embed/` once the Uno + applicator are built and the tool offset is measured. |
| **P3.3** | `proto_run.py` end-to-end: STL → slice → add pause(s) → stream → (dispense → press → shear → operator OK) → resume. |

Development Rules 4–7, 11–13 (`.CLAUDE/CLAUDE.md`) apply in full to P3.

---

## Open questions (resolve before the phase that needs them)

- **P2.1:** exact `CrealityPrint.exe` CLI syntax for CP 7 (flags, how the profile is
  passed, exit codes) — needs a 15-minute spike on the real install.
- **P2.2:** which filament profile is the day-to-day one (PETG per the sample slice?).
- **P1.3:** port the existing Tkinter panel, or take the chance to restructure it?
- **P3.2:** keep `proto/` and `magnet_embed/` as two packages, or fold the ported
  magnet code into `proto/` and retire `magnet_embed/`?

---

## References

- Creality Print (Orca-lineage) — https://github.com/CrealityOfficial/CrealityPrint
- CP CLI stability issue (3MF slice crash) — https://github.com/CrealityOfficial/CrealityPrint/issues/574
- OrcaSlicer CLI (fallback) — https://github.com/SoftFever/OrcaSlicer/wiki/Command-Line-Usage
- `stl-thumb` (bundled with Creality Print; STL preview) — https://github.com/unlimitedbacon/stl-thumb
- Printrun `printcore.py` (approach reference only — GPLv3, do not copy) —
  https://github.com/kliment/Printrun/blob/master/printrun/printcore.py
- Existing streaming-protocol notes — `project/BUILD_PLAN.md` → "Protocol notes"
