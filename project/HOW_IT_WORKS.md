# How It All Works — a plain-language walkthrough

This is the "explain it to me like I'm new" guide to the whole project. It goes
top to bottom: the idea, the hardware, the printer conversation, the software, and
what happens second-by-second when a magnet gets embedded. No prior knowledge of
3D-printer internals assumed.

For the terse reference version see `.CLAUDE/CLAUDE.md`; for the roadmap see
`project/PROJECT_PLAN.md`; for the code build order see `project/BUILD_PLAN.md`.

---

## 1. The idea in one paragraph

A normal 3D print is just plastic. We want some prints to have a **magnet baked
inside** them — for example a lid that snaps shut, or a panel that sticks to a
frame. The trick: print the part with a small **pocket** in it, stop the printer
when the pocket is finished, drop a magnet into the pocket, then let the printer
carry on and **print a "roof" over the magnet** so it's sealed inside. We're
building the machinery and software to do that stop / insert / resume cycle with
as little babysitting as possible.

---

## 2. The physical setup

```
   ┌──────────────┐     USB-C cable        ┌───────────────────────┐
   │  Windows PC   │ ─────────────────────▶ │  Creality Ender-3 V3 SE │
   │  (our software)│ ◀───────────────────── │  (the 3D printer)      │
   │              │     USB cable          ┌───────────────┐
   │              │ ─────────────────────▶ │  Arduino Uno   │ ──▶ servo ──▶ magnet magazine
   └──────────────┘ ◀───────────────────── └───────────────┘
```

- **The printer** is a stock Creality Ender-3 V3 SE. We do **not** modify its
  firmware. It speaks a standard language called **G-code** over its USB-C port.
- **The PC** runs our Python program. It sends the printer G-code one line at a
  time and listens for replies. It also talks to the Arduino.
- **The Arduino Uno** is a tiny separate computer. Its only job is to run **one
  servo motor** that pushes a single magnet out of a stacked magazine and onto a
  "holding pole" at the tip of a tool mounted next to the print nozzle.
- **The applicator** is a clip-on add-on that carries the magazine and the holding
  pole. It clips onto the printer's moving head. For now we assume it's mounted so
  it doesn't get in the way of ordinary printing.

Key point: **the Arduino only dispenses a magnet.** The actual *pressing* of the
magnet into the pocket and the *shearing* of the tool away from the magnet are
done by moving the **printer itself**. More on that in section 6.

---

## 3. How the PC talks to the printer

### G-code

G-code is a list of plain-text commands, one per line. A few you'll see a lot:

| Command | Meaning |
|---------|---------|
| `G0` / `G1 X10 Y20 Z0.4 F1500` | move to X=10, Y=20, Z=0.4 mm at feed 1500 mm/min |
| `G28` | "home" — drive to the corner until the endstop switches trip |
| `G90` / `G91` | switch to absolute / relative coordinates |
| `M82` / `M83` | switch the extruder (filament pusher) to absolute / relative |
| `M104 S200` / `M109 S200` | set nozzle to 200 °C / set **and wait** until it's there |
| `M400` | "finish every move you're still doing before replying" |
| `G92 E42` | "call the current filament position 42" (resets the counter) |

A sliced model (`.gcode` file) is thousands of these lines.

### The "ok" handshake

The printer has a small internal buffer. If we fire lines at it too fast we lose
some. So the rule (used by every 3D-printer host program) is:

> send one line → wait for the printer to reply `ok` → send the next line.

Our `GcodeRunner` does exactly this loop. If the printer says `wait` (it's idle)
or `busy: processing` (it's working on a slow command) we just keep waiting — those
are not errors.

### Why `M400` matters

Subtle but important: the printer replies `ok` as soon as a move is **queued**, not
when the nozzle has actually **finished moving**. That's fine for streaming a print
(you *want* the buffer kept full). But during a magnet insert we need to know the
head has truly stopped before the next step. So between every phase of the insert
we send `M400` — the printer withholds its `ok` until all motion is genuinely done.

### Pausing

To pause, we simply **stop sending lines**. The printer sits still, holding its
position and temperature, waiting for the next line. When we resume, we start
sending again. We never use the printer's own SD-card pause commands (`M0`/`M25`) —
the host is in full control.

---

## 4. The sentinel — how the software knows *where* to insert

We need a way to mark the exact spot in the G-code where the magnet goes in. We do
it with a **comment line** (comments start with `;` and the printer ignores them):

```
;MAGNET_INSERT X60 Y60 Z6 S+X
```

- `X60 Y60` — where the pocket is on the bed (millimetres)
- `Z6` — how high the magnet should sit (pocket floor + magnet thickness)
- `S+X` — which direction to slide the tool away afterwards (a direction with clearance)

A small tool (`gcode/postprocess.py`, being built in chunk C3) inserts this line
into a sliced file at the right layer. Because it's a comment:

- the file **still prints normally** straight from an SD card (the printer skips it), and
- our software **watches the stream** for a line starting with `;MAGNET_INSERT`,
  and when it sees one it runs the insert sequence instead of sending that line.

---

## 5. The tool offset

The magnet's holding pole is **not** at the same spot as the nozzle — it's mounted
a few centimetres to the side (and its tip is a little higher or lower). We measure
that fixed gap once and call it `magnet_tool_offset` = *(pole tip position) − (nozzle
tip position)*.

So to put the **pole** over a pocket at `(60, 60)` when the offset is `(30, 0, 5)`:

```
carriage moves to  (60 − 30, 60 − 0)  =  (30, 60)     ← nozzle goes here, pole ends up at (60,60)
nozzle presses to  Z = seat_z − 5                     ← so the pole tip lands at seat_z
```

Two consequences the software checks for:

1. **Reduced reach.** A pocket too close to the edge would need the carriage to go
   past its limit. The software computes every target and **refuses (leaves the
   print paused)** if anything is out of range.
2. **Minimum depth.** If the pole sits 5 mm above the nozzle, you physically can't
   push a magnet to a height below 5 mm. Same check catches it.

---

## 6. The insert sequence, step by step

When `GcodeRunner` hits the sentinel it calls `insert_magnet(...)`. Here's every
phase and *why* it's there. (Code: `magnet_embed/sequences/insert_magnet.py`.)

| Phase | What it sends | Why |
|-------|---------------|-----|
| **SAVE** | (reads current state) | Remember exactly where we were and how the printer was configured — position, filament counter, absolute/relative modes, feedrate, temperatures — so we can put it all back. |
| **PARK** | `M83`, retract filament a few mm, `G90`, lift Z to a safe height, `M400`, then `M104 S160` | Pull the filament back so it doesn't ooze during the pause. Lift up so travel moves clear the print. Drop the nozzle to a cooler "standby" temp (less oozing, less filament cooking) while we work. |
| **DISPENSE** | `dispenser.dispense()` (or asks the operator) | The Arduino cycles the servo so one magnet ends up stuck to the holding pole. In early testing there's no Arduino yet, so the software asks the human "magnet loaded? (ready/abort)". |
| **APPROACH** | `G90`, `G1 X.. Y..` to `pocket − offset`, `M400` | Move so the holding pole (not the nozzle) is directly above the pocket. |
| **PRESS** | `G1 Z..` down to `seat_z − offset.z` slowly, `G4` dwell, `M400` | Push the magnet down into the pocket. Slow feed and a short pause so it seats fully. There's no force sensor — we just go to a carefully chosen depth. |
| **SHEAR** | `G1 X.. Y..` a few mm sideways, `M400` | Slide the pole **sideways** off the magnet. Sideways, not straight up: the pocket walls stop the magnet from following the pole, so the magnet stays put while the pole peels away. Straight up would just pull the magnet back out. |
| **LIFT** | `G1 Z..` up to safe height, move to the park corner, `M400` | Get the tool clear of the part so the operator can look at it. |
| **ASK** | `prompt("confirm")` | The human checks the magnet went in correctly and answers **success**, **retry**, or **abort**. |
| **RESUME** | restore nozzle temp (`M104` then `M109` to wait), move back to the saved X/Y then Z, un-retract, `G92 E<saved>` to fix the filament counter, restore G90/G91 and M82/M83 and the feedrate | Undo everything PARK did, put the head back exactly where the print left off, and hand control back to the streamer. The next line of the file prints as if nothing happened. |

**Retry** loops back to DISPENSE (a fresh magnet) and tries again, up to a limit
(`sequence.max_retries`, default 3). **Abort** turns the nozzle off and stops.
If *anything* throws an error mid-sequence, the code still puts the nozzle
temperature back so the print stays resumable, then re-raises the error.

**No homing (`G28`) ever happens during a print** — homing would drag the nozzle
across the half-finished part and wreck it. Instead we trust the printer's step
counting and just move back to the saved coordinates.

---

## 7. The software, module by module

Everything lives under `magnet_embed/`.

| File | In plain terms |
|------|----------------|
| `config.py` + `config.yaml` | All the numbers (COM ports, the tool offset, speeds, temperatures, the park spot) live in one YAML file. `config.py` loads it and merges a private `config.local.yaml` on top for machine-specific values that shouldn't be shared. |
| `state.py` | Two simple data holders: `PrinterState` (where the printer is, how hot, what mode) and `MagnetInsert` (the four numbers parsed out of the sentinel). |
| `exceptions.py` | The named error types (`AckTimeout`, `OutOfEnvelopeError`, `SequenceAborted`, …) so failures are specific, not generic crashes. |
| `gcode/util.py` | Tiny text helpers: strip a `;` comment off a line; pull the numbers out of `G1 X10 Y20`. |
| `gcode/sentinel.py` | Recognises the `;MAGNET_INSERT ...` line and turns it into a `MagnetInsert`, or complains clearly if it's malformed. |
| `gcode/runner.py` | `GcodeRunner`: opens the `.gcode` file, runs the send-line / wait-for-`ok` loop, skips blank and comment lines, and calls our insert function when it sees the sentinel. Has `pause()` / `resume()` / `cancel()` that are safe to call from the UI thread. |
| `links/base.py` | The **contracts**: `PrinterLink` (anything that can take a G-code line and say `ok`) and `DispenserLink` (anything that can dispense a magnet). Real hardware and the fakes both obey these. |
| `links/printer_sim.py` | `SimPrinter` — a **pretend printer**. It reads G-code, keeps track of position / temperature / modes just like a real one would, and always answers `ok`. Lets us test the whole program on a laptop with nothing plugged in. |
| `links/dispenser_sim.py` | `SimDispenser` — a pretend Arduino. Counts how many magnets it "dispensed"; can be told to fail on purpose for testing. |
| `sequences/insert_magnet.py` | The step-by-step sequence from section 6. |
| `main_sim.py` | The command you run to see it all work in simulation: `python -m magnet_embed.main_sim tests/data/sample.gcode`. |

Not built yet: `gcode/postprocess.py` (C3, adds the sentinel to a sliced file),
`ui/panel.py` (C4, the Tkinter window), `links/printer_serial.py` +
`links/dispenser_serial.py` (C5, the real USB connections), `main.py` (C5,
the real-hardware entry point).

---

## 8. Why there's a simulator

The team rule (from `CLAUDE-COMMON.md`) is **write and test on the laptop first,
hardware last.** A bug found on a laptop costs a minute; a bug found on the printer
can cost a ruined print or a crashed nozzle.

So every piece of hardware has a **twin**:

- real printer ⟷ `SimPrinter`
- real Arduino ⟷ `SimDispenser`

They present the exact same interface and raise the exact same errors, so the
insert sequence, the runner, and (later) the UI can be run and tested end-to-end
with nothing plugged in. When we do plug in the real printer (chunk C5), only the
two `*_serial.py` files are new — everything above them is already proven.

There are **44 automated tests** (`pytest`) covering the sentinel parser, the
simulated printer's G-code handling, the streaming runner (including pause/cancel),
and every branch of the insert sequence (happy path, out-of-range, retry, abort,
dispenser failure, mode restore).

---

## 9. What a full run looks like (today, in simulation)

```
$ python -m magnet_embed.main_sim tests/data/sample.gcode

streaming tests/data/sample.gcode through SimPrinter
SENTINEL  X60.000 Y60.000 Z6.000 S+X  -> running insert sequence
magnet insert complete; printer restored to X60.00 Y60.00 Z6.00
insert sequence done -> resuming stream
done: 19/26 lines sent, 1 sentinel(s), 1 magnet(s) dispensed;
      final pos X80.00 Y80.00 Z8.00, nozzle 0/0
```

The stream ran, hit the marker, parked, dispensed, pressed, sheared, asked (auto-
answered "success" in this headless mode), put the printer back, and finished the
file.

---

## 10. Glossary

- **G-code** — the plain-text command language 3D printers and CNC machines speak.
- **Slicer** — software (Cura, Creality Print, PrusaSlicer) that turns a 3D model
  into G-code.
- **Host** — a program on a computer that drives a printer over USB (OctoPrint,
  Pronterface — and ours).
- **Firmware** — the software *inside* the printer (Marlin, on this machine). We
  don't touch it.
- **`ok` handshake** — send one line, wait for `ok`, send the next.
- **Sentinel** — our `;MAGNET_INSERT ...` marker comment.
- **Tool offset** — the fixed gap between the magnet pole and the print nozzle.
- **Envelope** — the box of positions the print head can physically reach.
- **Retract / prime** — pulling filament back / pushing it forward to stop or
  restart oozing.
- **Park** — moving the head to a safe out-of-the-way spot.
- **Shear** — the sideways move that leaves the magnet in the pocket and takes the
  pole away.
- **Simulator (`SimPrinter` / `SimDispenser`)** — fake hardware for laptop testing.
