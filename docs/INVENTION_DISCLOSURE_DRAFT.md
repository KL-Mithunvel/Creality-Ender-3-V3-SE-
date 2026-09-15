# Invention Disclosure — Working Draft

**Form:** Khurana & Khurana "Inventive Disclosure – Confidential" (`docs/Invention
DisclosureForm -Khurana & Khurana.docx`). This Markdown mirrors the form's 27
questions so answers can be reviewed in git and then pasted into the Word file.

> **Status: DRAFT for the inventors + the college teacher + the K&K patent agent to
> review and correct.** Claude drafted the technical answers from the project docs.
> Every `[INVENTORS TO COMPLETE]` / `[VERIFY]` marker needs a human.
>
> **Public-disclosure warning:** this project is in a git repository with a remote.
> If that repository is or becomes **public** (GitHub, etc.), or if the work is
> shown/published anywhere, that can count as a **public disclosure** and may bar or
> limit patent rights (India has a limited grace period; many countries have none).
> **Talk to the K&K agent before pushing this repo publicly or presenting the work.**
> As of this draft: no public disclosure has been made (see Q16).

---

## 1. Title of the Invention

*Working titles — pick one with the agent:*

- "Toolhead-Actuated System and Method for In-Situ Insertion of Discrete Magnets
  into Parts During Fused-Filament 3D Printing"
- "Host-Controlled Add-On for Automated Embedding of Permanent Magnets in 3D Prints
  Without Printer Firmware Modification"

## 2. Technical Field of the Invention (problem + solution + purpose)

**Field.** Additive manufacturing (fused-filament fabrication / FFF "3D printing");
specifically, automated insertion of discrete rigid components — here, permanent
magnets — into a part *while it is still being printed*, so subsequent layers seal
the component inside.

**Problem.** Embedding magnets (or nuts, bearings, RFID tags, etc.) in FFF prints
today is a **manual** operation: the operator adds a pause to the sliced file,
waits by the machine, and hand-places the component into an open pocket before
resuming. This is labour-intensive, hard to repeat consistently, error-prone for
component **orientation/polarity**, sensitive to how long the pause lasts (nozzle
ooze, part cooling), and does not scale to multiple inserts or unattended runs.
Existing automated approaches require either a dedicated multi-tool printer /
tool-changer, a separate pick-and-place machine and a second setup, or
modification of the printer's firmware.

**Solution.** A **clip-on applicator** for a standard, unmodified FFF printer plus
a **host program** on a PC. A single low-cost microcontroller (Arduino Uno) drives
**one servo** whose *only* function is to dispense **one magnet at a time** from a
magazine onto a small **magnetic holding pole** at the applicator tip. The
**printer's own motion system** then performs the two mechanical actions that
actually place the magnet: (a) a controlled **Z press** to seat the magnet in the
printed pocket, and (b) a short **lateral "shear" move** that slides the holding
pole off the seated magnet (the pocket walls resist the magnet moving sideways, so
it stays put). The insert location and parameters are carried in the sliced G-code
as a **comment "sentinel"** (`;MAGNET_INSERT X Y Z S<dir>`) that the printer
ignores but the host detects; on detecting it the host pauses the stream (by simply
not sending further lines), runs a park → dispense → approach → press → shear →
operator-confirm → resume sequence, and continues the print.

**Purpose.** Make embedded-magnet FFF parts producible with far less operator
effort and far better repeatability and polarity control, on inexpensive
off-the-shelf printers, with **no firmware changes** and with G-code that is still
valid for normal printing.

## 3. Search Terms

in-situ component embedding FFF; automated insert 3D printing; pause-and-insert
additive manufacturing; embedding permanent magnets 3D print; magnet insertion
fused filament fabrication; toolhead pick and place 3D printer; clip-on applicator
3D printer; G-code comment sentinel pause; host-controlled print pause insert;
magnetic holding pole dispenser; shear release placement; insert molding vs 3D
printing embedding; multi-material toolchanger embedding; nut/heat-set insert
during print; robotic magnet pick and place; Marlin host action pause; polarity
controlled magnet placement.

## 4. Background of the Invention (present state of the art)

**Present technologies**

1. **Manual pause-and-insert.** Slicer adds a pause (`M600` / `M0` / "pause at
   height"); operator hand-places the component; operator resumes. Widely
   documented (maker guides, slicer plugins).
2. **Dedicated tool-changing / multi-tool printers** (e.g. open-hardware
   tool-changers, IDEX machines) that could carry a placement tool — but require
   that class of printer and usually firmware support for the extra tool.
3. **Separate pick-and-place machines** used before/after printing, needing a
   second setup and precise part re-registration.
4. **Insert over-moulding** (injection moulding around an insert) — a different
   process, not additive, needs tooling.
5. **Continuous-fibre / metal-reinforced FFF** (e.g. Markforged) — embeds fibre,
   not discrete rigid components, via a dedicated print head.

**Limitations**

- Manual: operator time per insert; poor repeatability; frequent **polarity**
  mistakes; pause-duration side effects (ooze, layer shift, adhesion loss); does
  not scale to many inserts or unattended operation.
- Tool-changer / multi-tool: expensive printer class; often needs firmware
  changes; overkill for a single insert type.
- Separate pick-and-place: second machine, second setup, re-registration error.
- Over-moulding: not additive; hard tooling; minimum volumes.
- Fibre systems: don't address discrete magnets/nuts/etc.; proprietary hardware.

## 5. Prior Art (known products / processes / patents / publications)

*Non-exhaustive; a formal patent search must be run by the K&K agent (see Q19).
Full notes + links in `project/RESEARCH.md`.*

**Closest published work — automated in-situ placement (must be cited):**
- **"Automated In-Situ Placing of Metal Components Into 3D Printed FFF Objects"**,
  IEEE, May 2021 (Plätzsch et al.). Modified Prusa i3 with a **powered electromagnet
  gripper** on a hollow-shaft NEMA 8 stepper + slip-ring (unlimited rotation); an
  **augmented slicer** auto-generates cavities + placement G-code; parts staged on a
  **printed bed tray**; **two cameras + OpenCV** align each part; controlled by the
  **OctoPNP** OctoPrint plugin. https://ieeexplore.ieee.org/document/9426422/
- **OctoPNP** — `github.com/platsch/OctoPNP` — OctoPrint plugin for camera-assisted
  pick-and-place in 3D printers (tray + head cam + bed cam + OpenCV).
- **"3D-Printable Electronics — Integration of SMD Placement and Wiring into the
  Slicing Process for FDM"** (2017); **"Embedding of SMD populated circuits into FDM
  printed objects"** (2017); **"Towards Integrating 3D Printing and Automated
  Assembly"** (2023); **"Printegrated Circuits"** (arXiv 2025).

**Host-side pause / marker mechanics:**
- **OctoPrint `@` commands** — `@pause` etc. placed in the G-code are never sent to
  the printer, they trigger host functions. (Our `;MAGNET_INSERT` comment is the same
  idea, made SD-safe and carrying parameters.)
- **OctoPrint-GCodeSystemCommands** plugin — map a G-code to a shell/Python action
  (people drive a servo for nozzle cleaning this way).
- **Klipper** `PAUSE`/`RESUME` macros with `SET_GCODE_VARIABLE` state save/restore;
  **Marlin** `M125` / `PARK_HEAD_ON_PAUSE` / `M600` (firmware-side park & restore).
- Slicer "Pause at height" / `M601` (Cura, PrusaSlicer, Creality Print) — the manual
  pause-and-insert method.

**Other:**
- Open-hardware tool-changers (Jubilee; E3D tool-changer) — tool-offset handling,
  multiple toolheads on one motion system.
- DIY pick-and-place (3DPlacer, Micro_PNP, Picktor, LumenPnP, OpenPnP) — vacuum
  pickup, feeders, rotation, bottom vision.
- 3D-printer host software (Printrun/Pronterface, OctoPrint) — host-controlled
  G-code streaming and pausing.
- Maker/vendor guides on embedding hardware (Markforged; MLC-CAD; forums) — the
  pocket + pause + seal concept, pocket oversize ~0.1–0.3 mm, 2–3 cap layers.

- `[INVENTORS/AGENT TO COMPLETE]` — **patent** search (Espacenet / Google Patents /
  Indian Patent Advanced Search / WIPO) for: automated insertion during additive
  manufacturing; magnetic component placement heads; marker/sentinel-driven print
  interruption; in-situ component embedding.

## 6. Has the work filled a major gap in the prior art? Describe the gap.

**Yes (subject to the formal search).** The published automated approach (IEEE 2021 /
OctoPNP, Q5) closes the automation gap only with a **heavy, instrumented rig**: a
dedicated powered electromagnet gripper on its own rotary stepper, two cameras with
vision processing, a custom slicer, and a firmware/plugin that ideally manages tool
offsets. That is a research platform, not something a hobbyist bolts onto a stock
printer.

The remaining gap this project targets: automated, repeatable, polarity-correct
insertion on a **stock, unmodified, single-tool consumer printer** with **no added
placement actuator and no vision**. It closes that gap by (i) using the **printer's
own motion** for the seating press and a **lateral shear** release (pocket wall as
the reaction feature), so the only added actuator is a single-servo **feeder**;
(ii) an **inert G-code comment** marker so there is **no firmware or slicer change**
and the file still prints normally from SD; and (iii) a host-side tool-offset
transform with an envelope guard, since the firmware is untouched.

## 7. Components of the Invention

**External / physical**

- **A1. Clip-on applicator body** — mounts to the existing print carriage; assumed
  not to interfere with normal printing (removable clip).
- **A2. Magnet magazine** — holds a stack/column of identical magnets; includes an
  **escapement** that isolates exactly one magnet against magnet-to-magnet
  attraction. `[design in progress]`
- **A3. Servo actuator** — one hobby servo; the only powered motion the add-on has.
- **A4. Magnetic holding pole** — a small pole/pole-piece at the applicator tip
  that retains a single dispensed magnet by magnetic attraction and **fixes its
  polarity/orientation** (all magazine magnets load the same way).
- **A5. Arduino Uno microcontroller** — drives A3; USB serial to the host.
- **A6. Separate 5–6 V servo power supply** with common ground.
- **A7. Standard FFF printer** (Creality Ender-3 V3 SE), unmodified, USB-C serial.
- **A8. Host computer** (Windows PC) running the control software.
- **A9. The printed part**, designed with **A10. a magnet pocket** (slightly
  oversized, optionally with a retention undercut / adhesive), positioned within the
  offset-reachable area of the bed, and covered by "cap" layers after insertion.

**Internal / software blocks** (running on A8)

- **B1. G-code post-processor** — inserts the sentinel comment
  `;MAGNET_INSERT X Y Z S<dir>` into a sliced file at the chosen layer.
- **B2. Streaming runner** — sends G-code line-by-line, waits for `ok`, detects the
  sentinel, pauses by withholding lines.
- **B3. Sentinel parser** — extracts pocket X/Y, seat height Z, shear direction.
- **B4. Tool-offset transform + envelope check** — converts pocket coordinates to
  carriage targets using the measured pole-to-nozzle offset; refuses out-of-range
  targets with the print left safely paused.
- **B5. Insert sequence state machine** — SAVE → PARK → DISPENSE → APPROACH →
  PRESS → SHEAR → LIFT → ASK(operator) → RESUME; each phase gated by `M400`;
  never homes mid-print.
- **B6. Dispenser link** — serial protocol to A5 (`PING`/`DISPENSE`/`RESET`/`STATUS`).
- **B7. Operator interface** — confirm / retry / abort prompt; jog controls.
- **B8. Simulation layer** — software twins of A7 and A5 for development/testing.
- **B9. Arduino firmware** — receives `DISPENSE`, cycles the servo through one
  escapement stroke, reports `OK` / `ERR`; idle watchdog safes the servo.
- **B10. Insert planner + preview** — a dialog in which the operator enters the
  pocket position, seat height, release direction and target layer; it computes
  the carriage moves from the *same* geometry function B5 executes, draws the
  planned nozzle and pole paths over the sliced part (plan view and side view,
  plus an animated play/scrub view), runs the B4 check live as the fields
  change, and writes the sentinel into a copy of the file. "What is previewed
  is what runs" — the preview cannot drift from the executed motion.
- **B11. Firmware-pause substitution** — the streaming runner recognises the
  slicer/firmware pause codes (`M0`, `M1`, `M25`, `M600`, `M601`) and withholds
  them, because the host owns the pause and B5 does the parking. The
  post-processor can optionally write a real `M0` next to the sentinel, so a
  single file both pauses correctly when printed from the SD card (manual
  insert) and streams cleanly through the host (automated insert).

## 8. How the Invention works

1. The part is designed with a magnet pocket ending a few layers below its top
   surface; it is sliced normally.
2. **B1** inserts one `;MAGNET_INSERT X Y Z S<dir>` comment at the layer where the
   pocket is complete. The file is still SD-printable (printer ignores comments).
3. The host (**B2**) streams the file to the printer, one line per `ok`.
4. On seeing the sentinel, **B2** stops sending lines (the printer holds position
   and temperature) and calls **B5** with the parsed values from **B3**.
5. **B4** computes the carriage target = pocket − offset and the press depth =
   seat_z − offset_z, and checks all targets are reachable; if not, it aborts with
   the print still paused. The same check (implemented 2026-09-16, see Q9
   item 7) also tests the nozzle position during PRESS and along SHEAR against
   the printed part's own footprint, derived from the sliced toolpath, and
   refuses a press into the build plate — so the nozzle can never be driven
   into the plate or the partly-printed part while the pole seats the magnet.
   The operator-facing planner (**B10**) runs the identical function and
   reports each reason in plain language.
6. **B5** runs:
   - **SAVE** the current position, filament counter, coordinate/extruder modes,
     feedrate, temperatures.
   - **PARK**: retract filament; lift Z to a safe clearance; set the nozzle to a
     cooler standby temperature.
   - **DISPENSE**: host sends `DISPENSE` to **B6→A5**; the servo (**A3**) cycles the
     escapement (**A2**) so one magnet transfers onto the holding pole (**A4**),
     which fixes its polarity. (During early development a human loads the magnet on
     an operator prompt.)
   - **APPROACH**: move the carriage so **A4** is above the pocket.
   - **PRESS**: drive Z down slowly to `seat_z − offset_z`, dwell briefly — the
     printer's Z axis pushes the magnet into the pocket (**A10**).
   - **SHEAR**: move the carriage a few millimetres **laterally** in `S<dir>`. The
     pocket walls hold the magnet; the holding pole slides off it. (Lateral, not
     vertical — vertical would pull the magnet out.)
   - **LIFT** clear; **ASK** the operator: success / retry / abort.
   - **RESUME**: restore nozzle temperature (wait), move the head back to the exact
     saved position, un-retract, correct the filament counter, restore modes and
     feedrate.
7. **B2** resumes streaming from the next line; subsequent "cap" layers print over
   the magnet, sealing it inside the part.
8. Every phase transition uses `M400` so the host acts only after motion truly
   completes. The sequence never issues `G28` (homing) because that would collide
   with the partly-printed part; it relies on the printer's step counting and
   returns to saved coordinates.

## 9. Novelty / Inventive Step

Candidate novel aspects (for the agent to sharpen into claims):

1. **Division of labour**: the added mechanism performs **only single-magnet
   dispensing**; the **printer's existing motion system performs the seating press
   and the release**, eliminating any dedicated placement actuator.
2. **Lateral shear-release** of a magnetically-held component into a printed pocket,
   using the pocket geometry as the reaction feature so the component is not
   withdrawn.
3. **Sentinel-as-inert-comment**: insert location/parameters embedded in standard
   G-code as a comment that requires **no firmware or slicer modification** and
   leaves the file normally printable, with a host that pauses purely by
   flow-control (withholding lines).
4. **Deterministic polarity** by construction — a magnetic holding pole plus a
   uniformly-loaded magazine fixes orientation without sensing or per-part marking.
5. **Tool-offset transform with an in-envelope guard** and a **no-homing**,
   `M400`-gated, fully state-restoring interrupt/resume routine specific to
   mid-print component insertion on a single-tool machine.
6. **Clip-on, printer-agnostic** add-on: works on an unmodified consumer printer.
7. **Collision-aware placement check using the part's own toolpath.** Because
   the pole is offset from the nozzle, seating the magnet puts the *nozzle* at a
   different XY and, with a pole tip above the nozzle, *below* the seat height.
   The host derives the printed part's footprint and local height from the
   sliced G-code it is already streaming and refuses any PRESS/SHEAR whose
   nozzle position would lie inside the partly-printed part. A bed-limit check
   alone cannot catch this; the toolpath-derived check is specific to
   single-tool, offset-tool insertion.
8. **Pause-code substitution for one dual-use file.** The host withholds
   firmware pause codes and runs its own park/insert/resume routine in their
   place, so a file carrying both a conventional pause and the sentinel prints
   correctly from the SD card (operator inserts by hand) *and* through the host
   (automated insert) without re-slicing.
9. **Preview-equals-execution planning.** The operator-facing planner draws and
   envelope-checks the identical geometry the run executes (one shared
   function), so the previewed motion is the commanded motion by construction.

## 10. Advantages / improvements over existing methods

- Removes the operator from the per-insert loop → **less labour, more repeatable**.
- **Polarity is guaranteed**, not operator-dependent.
- **No dedicated placement actuator** → cheaper, lighter add-on (one servo).
- **No firmware or slicer modification**; sliced file still prints from SD.
- Works on **low-cost single-tool printers**, not just tool-changers.
- **Envelope check + no mid-print homing + full state restore** → lower risk of
  crashes / ruined prints than ad-hoc manual resumes.
- Standby-temp + retract handling reduces **ooze / layer-shift** artefacts common
  to long manual pauses.
- Scales toward **multiple inserts per part** (multiple sentinels) and, later,
  unattended operation.
- `[VERIFY against the closest patents once the search is done.]`

## 11. Alternative embodiments / variants

- **Other components**: nuts, threaded inserts, bearings, RFID/NFC tags, PCBs,
  electrical contacts, weights, decorative elements — same dispense/press/shear.
- **Dispenser variants**: rotary carousel; gravity magazine + solenoid escapement;
  vibratory feeder; belt feeder; multi-magazine for mixed components.
- **Retention variants**: press-fit pocket; pocket + dispensed adhesive; passive
  spring-loaded stripper plate instead of (or with) the lateral shear.
- **Release variants**: lateral shear (baseline); controlled rotation; passive
  fixed stripper engaged by the LIFT move; powered ejector as a fallback.
- **Staging variants**: a magazine on the toolhead (baseline); a **printed part-tray
  clipped to the bed** that the tool picks from per-print (as in OctoPNP); an external
  hopper/chute feeding the pole.
- **Marker variants**: dedicated MCU pin/output instead of a G-code comment; a
  distinct unused G-code word; an OctoPrint `@`-command; a separate side-car file
  keyed to layer number; a slicer plugin that emits the sentinel directly.
- **Motion variants**: press by servo instead of Z (hybrid); tool raised/lowered by
  a second servo for printers where clearance is tight.
- **Pole-height variants (offset-Z sign)** — the key mechanical trade-off:
  - *Pole tip above the nozzle tip* (positive Z offset; current baseline): the
    applicator never touches the part during normal printing, but the nozzle
    descends below the seat height while pressing, so the pocket must lie within
    the lateral offset distance of the part's edge (nozzle lands outside the
    footprint) and the host enforces the toolpath collision check (Q9 item 7).
  - *Pole tip below the nozzle tip* (negative Z offset): any pocket location is
    reachable, but the pole would foul normal printing unless it is deployable.
  - *Deployable pole*: the pole retracts above the nozzle during printing and is
    deployed only for the insert — by the same single servo that dispenses (its
    stroke both isolates a magnet and lowers the pole), by a passive latch the
    printer engages by moving against a fixed post at the bed edge (no extra
    actuator), or by a second servo. In every variant the printer's motion still
    performs the press and the lateral shear.
- **Pocket-placement variant**: the part is designed so the pocket sits within
  the offset distance of an outer edge, removing the need for a deployable pole
  at the cost of a design constraint.
- **Control variants**: fully automated confirmation via a hall-effect / vision
  check of the pole instead of an operator prompt; migration to Klipper macros;
  Raspberry Pi host; networked/headless operation.
- **Printer variants**: any FFF printer with USB/serial G-code; CoreXY; bed-slinger;
  tool-changer carrying this as one tool.
- **Magnet variants**: different grades/sizes; high-temp grades where cap-layer
  reheat risks demagnetisation; pre-magnetised arrays.

## 12. CAD images / line diagrams of the final prototype

`[INVENTORS TO COMPLETE]` — not yet available (prototype not built). Required:

- Applicator assembly (magazine, escapement, servo, holding pole) mounted on the
  print carriage — one **fully labelled** set, one **unlabelled** set.
- Section view of a magnet seated in a printed pocket with cap layers.
- **Flow chart** of the insert state machine (SAVE→…→RESUME) — can be generated
  from `project/PROJECT_PLAN.md` §4 / `project/HOW_IT_WORKS.md` §6.
- Diagram of the tool-offset geometry (nozzle vs pole, carriage target = pocket −
  offset).
- System block diagram (PC ↔ printer ↔ Arduino ↔ servo) — see
  `project/HOW_IT_WORKS.md` §2.

## 13. Inventor's description of the images/drawings

`[INVENTORS TO COMPLETE once drawings exist.]` Base narrative available in
`project/HOW_IT_WORKS.md` (plain-language) and `.CLAUDE/CLAUDE.md` (technical).

## 14. Complete description incl. working example / methodology

See Q7 (components) + Q8 (operation). Worked example (simulation, current build):

- Part: test coupon, magnet pocket centred at bed (60, 60), pocket floor such that
  seat height Z = 6 mm, cap = 4 layers.
- Sentinel injected at the layer covering the pocket:
  `;MAGNET_INSERT X60 Y60 Z6 S+X`.
- Measured tool offset (example): (30, 0, 5) mm (pole 30 mm +X of nozzle, tip 5 mm
  above nozzle tip).
- Host computes: carriage approach = (30, 60); press nozzle Z = 6 − 5 = 1 mm;
  shear target = (35, 60). All within the 220 × 220 × 250 mm envelope → proceed.
- The host emits the following commands, phase by phase (exactly what the
  current implementation sends; `saved.*` are the values captured at SAVE, the
  print position here is (60, 60, 6) with nozzle target 200 °C):

  | Phase | Commands sent to the printer | Purpose |
  |-------|------------------------------|---------|
  | SAVE | `M400`, `M114` (read back) | Record X Y Z E, feedrate, G90/G91, M82/M83, temperatures |
  | PARK | `M83` · `G1 E-3 F2400` · `G90` · `G1 Z21 F6000` · `M400` · `M104 S160` | Relative extrusion; retract 3 mm; lift to safe Z (saved Z + 15); wait; nozzle to standby |
  | DISPENSE | `DISPENSE` → Uno (or operator prompt) | One magnet onto the holding pole |
  | APPROACH | `G90` · `G1 X30 Y60 F6000` · `M400` | Carriage to pocket − offset, pole now over the pocket |
  | PRESS | `G1 Z1 F60` · `G4 P500` · `M400` | Slow Z press to seat_z − offset_z; dwell 0.5 s; wait |
  | SHEAR | `G1 X35 Y60 F1200` · `M400` | 5 mm lateral move in +X; pole slides off the seated magnet |
  | LIFT | `G1 Z21 F6000` · `G1 X5 Y5 F6000` · `M400` | Clear the part; move to the park corner |
  | ASK | operator prompt → success / retry / abort | Retry re-enters at DISPENSE (`RESET` sent to the Uno first) |
  | RESUME | `M104 S200` · `M109 S200` · `G90` · `G1 Z21 F6000` · `G1 X60 Y60 F6000` · `M400` · `G1 Z6 F6000` · `M400` · `M83` · `G1 E2 F300` · `G92 E<saved E>` · `M82`/`M83` · `G90`/`G91` · `G1 F<saved feed>` | Reheat and wait; return at safe Z, then descend; un-retract/prime; restore the E reference and every modal state |

  No `G28` appears anywhere; every phase ends with `M400` so the host acts only
  on completed motion. On any error the nozzle target is restored (or set to 0
  on an operator abort) and the print is left paused and resumable.
- Print resumes; cap layers seal the magnet.
- Verified end-to-end against a simulated printer + simulated dispenser; **225
  automated tests** pass, including a full-workflow test (slice → plan → save →
  stream → sentinel → insert → resume → end of file) and the out-of-envelope
  abort path. The **printer serial link has run on the real machine** (Ender-3
  V3 SE over USB, 2026-09-09) and a real sliced part was streamed through the
  host on 2026-09-15 — no magnet insert on hardware yet.
- Note on this worked example: with the baseline offset the nozzle presses at
  X30 Y60 Z1. For a coupon whose footprint spans X 40..80 that point is clear
  of the part and the plan is accepted; for a coupon spanning X 0..80 it lies
  *inside* the part and the toolpath collision check (Q9 item 7, implemented)
  refuses the plan with the reason — the pocket must sit within 30 mm of the
  part's −X edge for a pole-above-nozzle applicator, or a deployable pole is
  needed (Q11).

Broad workable parameter ranges: see Q21.

## 15. Experiments conducted / third-party validation

**No magnet insert on hardware yet.** Validation so far:

- **Software simulation** — `SimPrinter` / `SimDispenser`, 225 `pytest` cases
  covering the parser, post-processor, streaming runner, every branch of the
  insert state machine, the planner geometry, the UI mediator, and the serial
  links driven by a fake port.
- **Real printer, serial control** — 2026-09-09: the host connected to the
  Ender-3 V3 SE over USB, completed the `M115` handshake and read position via
  `M400`/`M114`. 2026-09-15: a real sliced part (46 layers, PETG) was streamed
  through the host and printed; jog, home, temperature control and bed levelling
  were exercised from the panel. This confirms the streaming/flow-control layer
  on stock firmware; the sentinel path was not exercised on hardware.
- **Not yet done** (`project/PROJECT_PLAN.md` §5): applicator build; servo-alone
  test; cold "air-insert" of APPROACH/PRESS/SHEAR/LIFT; magnet-near-bed
  attraction; nozzle idle-timeout; first coupon with a real magnet. `[Fill in
  results as they happen.]`
- No third-party validation.

## 16. Public disclosure / publication

**None as of this draft (re-confirmed 2026-09-16).** The project exists in a
git repository on the inventors' machine with a remote at
`github.com/KL-Mithunvel/Creality-Ender-3-V3-SE-`, which the owner confirms is
**private** (not publicly visible). **No** paper, poster, video, demo, sale, or
public repo. `[If this changes, record the date and forum here and tell the K&K
agent immediately — it affects filing deadlines and foreign rights. Keep the
repository private until the agent clears publication.]`

## 17. Stage / level of development

**Early, with the control software complete.** Concept fully formulated and
specified; the host software (streaming, sentinel, insert state machine,
planner/preview, control panel, run logging, calibration aids) is **complete
for the operator-assisted phase and validated in simulation**; the printer
control layer is **validated on the real printer** (serial control and a real
print streamed through the host). The mechanism (magazine / escapement /
holding pole / mount) is designed on paper, **not built**; the Arduino sketch is
not written; **no magnet insert has been performed on hardware**.
→ Between "basic conceptualization" and "experimental proof of concept". (See
Q26 — TRL 3, partial.)

## 18. Aspects to claim / monopolise (proposed claims — for the agent to draft)

Indicative directions only:

1. A method of embedding a discrete component in a part during FFF printing,
   comprising: injecting an inert marker into the toolpath; a host detecting the
   marker and pausing by withholding toolpath commands; dispensing a single
   component onto a holding feature of a carriage-mounted applicator; and **using
   the printer's motion system to press the component into a pocket and to perform a
   lateral relative move that releases the component from the holding feature while
   pocket geometry retains it**; then restoring state and resuming.
2. The method where the marker is a G-code comment carrying insert coordinates,
   seat height, and release direction, such that the toolpath remains valid for
   unmodified printing.
3. The method where component orientation/polarity is fixed by a magnetic holding
   feature and a uniformly-loaded magazine, without sensing.
4. The method with a coordinate transform from component-frame to carriage-frame
   using a fixed tool offset, and an in-envelope check that aborts with the print
   paused rather than commanding an out-of-range move.
5. The method performed **without printer firmware modification** and **without
   homing during the print**, with each phase gated by a finish-moves command.
6. An **apparatus**: a clip-on FFF applicator whose only actuator is a
   single-component dispenser, relying on the host + printer motion for placement.
7. The method of claim 4 where the check further derives the **footprint and
   local height of the partly-printed part from the toolpath being streamed**
   and rejects any press or release move that would place the printer's own
   nozzle (or applicator body) inside that part.
8. The method where the host **withholds firmware pause commands** present in
   the toolpath and performs its own pause/insert/resume in their place, such
   that one toolpath file supports both manual insertion when printed
   standalone and automated insertion when streamed.
9. The method where the operator-facing planning step **computes, displays and
   checks the placement motion with the same function that later commands
   it**, and writes the marker into the toolpath.
10. The apparatus of claim 6 where the holding feature is **deployable** between
    a retracted position clear of normal printing and a deployed position below
    the nozzle tip, actuated by the same dispenser actuator, by a passive
    engagement the printer's motion performs, or by a second actuator.
11. Dependent claims: escapement isolating one magnet against mutual attraction;
    standby-temperature and retract handling during the pause; operator
    confirm/retry loop with dispenser reset; multi-marker / multi-insert;
    adhesive-assisted retention; passive stripper variant; non-magnet
    components; pocket positioned within the offset distance of a part edge.

## 19. Novelty / inventiveness search done?

Informal web/literature review is done — see **`project/RESEARCH.md`** (academic
papers, OctoPNP, host-control docs, maker practice) and the notes in Q5. It found
the IEEE 2021 / OctoPNP line of work as the closest published art. **No formal
patent-database search has been done** (Espacenet / Google Patents / Indian Patent
Advanced Search / WIPO PATENTSCOPE) — the K&K agent should run it. Table to fill:

| S.no | Reference | Existing idea | Our invention |
|------|-----------|---------------|---------------|
| 1 | IEEE 2021 "Automated In-Situ Placing…" / OctoPNP | automated in-situ placement via a **powered electromagnet gripper + rotary stepper + 2 cameras + custom slicer + OctoPrint plugin** on a modified Prusa | **no placement actuator** (servo only feeds); **printer motion** does press + **lateral shear** release; **no vision**; **inert comment** marker; **stock firmware**; single operator-confirm |
| 2 | manual pause-and-insert guides (Markforged, forums) | operator hand-places a component during a slicer pause | automated dispense; polarity fixed by the holding pole; no operator per insert |
| 3 | OctoPrint `@pause` / GCodeSystemCommands | in-stream marker triggers a host action / external script | same mechanism, but a **`;` comment** (SD-safe) carrying **placement coordinates**, driving a full park→place→shear→resume routine |
| 4 | tool-changer projects (Jubilee, E3D) | multiple toolheads on one motion system, often needs firmware support | one **passive** feeder tool; placement by existing motion; no firmware change |
| 5 | `[patent search results — AGENT]` | | |

## 20. Would a person of ordinary skill have arrived at this?

Proposed answer: **No — not obviously.** Reasons to develop with the agent: the
prior art points toward *either* keeping a human in the loop *or* adding a
dedicated placement actuator / special printer; the specific combination —
inert-comment marker + host flow-control pause + **re-using the print motion for
both press and a lateral shear-release keyed to pocket geometry** + single-servo
feeder + no-homing state-restoring resume — is a non-obvious way to get automated,
repeatable, polarity-correct insertion on a stock single-tool printer. `[Inventors
to add their own reasoning; agent to test against the search.]`

## 21. Broad workable ranges for the parameters

*(Design intent / simulation defaults; confirm on hardware.)*

| Parameter | Working range (indicative) | Current default |
|-----------|----------------------------|-----------------|
| Magnet diameter | 3–15 mm | `[TBD]` |
| Magnet thickness | 1–5 mm | `[TBD]` |
| Pocket clearance (per side) | +0.05 to +0.30 mm | `[TBD]` |
| Cap layers over magnet | 2–8 | `[TBD]` |
| Tool offset X/Y | any, subject to reachable envelope; the reachable pole area is the bed minus a border of the offset on two sides | 30 / 0 mm |
| Tool offset Z (pole tip − nozzle tip; **+ = pole above nozzle**) | −10 to +15 mm. Positive: pocket must be within the X/Y offset of a part edge or a deployable pole is used (Q11). Negative: any pocket reachable, pole must deploy/retract. | +5 mm |
| Safe Z lift before travel (above the paused print height) | 5–30 mm; must clear the applicator body over the tallest printed feature | 15 mm |
| Retract before pause | 1–6 mm @ 1200–3000 mm/min | 3 mm @ 2400 |
| Standby nozzle temp during pause | (soften pt) to (print − 20 °C), or fully off | 160 °C |
| Press feed (Z into pocket) | 20–120 mm/min; press is **open-loop** (commanded depth, no force sensing) | 60 mm/min |
| Press over-travel below the nominal seat (proposed parameter) | 0–0.3 mm | not yet implemented |
| Press dwell | 100–1000 ms | 500 ms |
| Shear distance | 2–10 mm | 5 mm |
| Shear feed | 300–3000 mm/min | 1200 mm/min |
| Operator retries before abort | 0–5 | 3 |
| Serial baud (printer) | 115200 (this printer) | 115200 |
| Build volume (this printer) | 220 × 220 × 250 mm | — |

## 22. Commercialisation data (2–5 companies)

`[INVENTORS/AGENT TO COMPLETE — names + full addresses of companies who might
manufacture/licence this.]` Categories to consider: desktop 3D-printer OEMs;
3D-printer accessory/upgrade makers; automation-integration firms; magnet
suppliers with assembly services; contract manufacturers doing embedded-electronics
prints. **Do not list companies without checking** — this section must be real.

Short marketing profile: `[to be written]` — 1 paragraph: the add-on turns a
sub-$300 printer into a machine that produces embedded-magnet parts hands-free,
with guaranteed polarity, no firmware voiding, at a fraction of a tool-changer's
cost.

## 23. Market potential / size / trends

`[INVENTORS/AGENT TO COMPLETE with cited sources — do not invent figures.]`

| Year | Estimated market size | Growth drivers | Notable existing devices |
|------|----------------------|----------------|--------------------------|
| | `[cite a source]` | desktop FFF adoption; demand for functional/assembled prints; magnet use in enclosures, jigs, toys, medical models | tool-changer printers; manual pause-insert workflow |

## 24. Inventors

1. kl mithunvel — `<klm@smtw.in>` — `[full legal name, address, nationality]`
2. `[FRIEND'S FULL LEGAL NAME]` — `[email, address, nationality]`
3. `[Teacher / guide — confirm with them whether they are an inventor (made an
   inventive contribution) or only a facilitator. Institutions often have IP
   assignment rules — check your college's policy before filing.]`

## 25. User Information

- **a. Potential users:** 3D-printing hobbyists and makers; product designers /
  prototypers; small manufacturers of enclosures, jigs & fixtures, educational and
  medical models, toys, consumer goods with magnetic closures; university/maker
  labs; 3D-printer OEMs (as a built-in feature).
- **b. Age group:** adults; hobbyist and professional (≈16+; primarily 20–55).
- **c. Expected benefits:** hands-free, repeatable magnet embedding; correct
  polarity every time; fewer failed prints from manual resumes; ability to batch
  parts; no loss of printer warranty/firmware.
- **d. Cost advantage:** one servo + an Arduino Uno + printed clip-on parts vs. a
  tool-changer printer (10–30× the machine cost) or a separate pick-and-place
  setup; vs. manual labour, it removes operator minutes per insert. `[quantify
  once BOM is fixed]`

## 26. Technology Readiness Level

**TRL 3 (partial).** TRL 2 (technology concept formulated) is met; TRL 3
(experimental proof of concept) is **partially** met — the control method is
proven in software simulation, and the host-to-printer control layer (stock
firmware, no modification) is proven on the real printer including a complete
streamed print. The insertion mechanism itself has not been built or tested.
Not yet TRL 4 (lab validation of the whole system).
→ Tick **TRL 2** and **TRL 3** (partial), Research phase.

## 27. Additional notes / remarks

- The host software is complete for the operator-assisted phase
  (`project/BUILD_PLAN.md`, chunks C1–C24): config, simulated + real
  printer/dispenser links, sentinel parser + post-processor, streaming runner
  with firmware-pause substitution, the full park→dispense→press→shear→resume
  insert state machine, a shared insert-geometry module, the insert planner
  with live preview and animated motion, a Tkinter control panel with a live
  print view, bed-levelling and Z-offset calibration aids, and per-run logging —
  **225 automated tests**. The printer control layer has been exercised on the
  real Ender-3 V3 SE (serial handshake 2026-09-09; a full real print streamed
  2026-09-15). The physical mechanism (magazine / escapement / holding pole /
  mount) and the Arduino sketch are **not yet built**; no magnet insert has
  been performed on hardware.
- Known design issue recorded 2026-09-16 and reflected in Q8/Q9/Q11/Q18/Q21:
  with the pole tip above the nozzle, the nozzle can be driven into the printed
  part during PRESS unless the pocket is near a part edge. The toolpath-derived
  collision check is now implemented in the host (planner, preview and run
  share it; 245 automated tests); the deployable-pole embodiment remains a
  design option. Both are disclosed so they are covered regardless of which
  the prototype adopts. An emergency-stop control (`M112`) was added to the
  operator interface at the same time.
- Reference material and prior-art notes: **`project/RESEARCH.md`** (comprehensive)
  and `project/BUILD_PLAN.md` → References (protocol-focused).
- **Before any public disclosure or repo publication, consult the K&K agent** (see
  the warning at the top).
- Confirm **college IP-ownership policy** and the teacher's role before filing.
