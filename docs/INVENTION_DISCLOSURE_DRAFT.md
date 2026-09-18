# Invention Disclosure — Working Draft

| | |
|--|--|
| **Form** | Khurana & Khurana "Inventive Disclosure – Confidential" — `docs/Invention DisclosureForm -Khurana & Khurana.docx` (27 questions). This Markdown mirrors the form one-to-one so answers can be reviewed in git and then pasted into the Word file. |
| **Status** | **DRAFT** for the inventors, the college guide and the K&K patent agent to review and correct. Claude drafted the technical answers from the project docs and code. |
| **Last updated** | 2026-09-18 — brought to the state of software chunk C31 (262 automated tests). Previous refresh 2026-09-16 (C24 → C25). |
| **Source material** | `.CLAUDE/CLAUDE.md` (technical brief), `project/PROJECT_PLAN.md`, `project/BUILD_PLAN.md`, `project/HOW_IT_WORKS.md`, `project/RESEARCH.md`, `magnet_embed/` (code), `magnet_embed/config.yaml` (defaults). |

**Placeholder legend** — every marker below needs a human before the form is submitted:

| Marker | Who | Meaning |
|--------|-----|---------|
| `[INVENTORS TO COMPLETE]` | inventors | Facts only the inventors have (names, drawings, measurements, companies). |
| `[AGENT]` | K&K agent | Formal patent search, claim drafting, market data. |
| `[VERIFY]` | inventors + agent | A drafted statement that must be checked before it is relied on. |
| `[TBD]` | inventors | A number not yet measured on hardware. |

> **Public-disclosure warning.** This project lives in a git repository with a
> remote. If that repository is or becomes **public** (GitHub etc.), or if the work
> is shown, demonstrated or published anywhere, that can count as a **public
> disclosure** and may bar or limit patent rights (India has a limited grace
> period; many countries have none). **Talk to the K&K agent before pushing this
> repo publicly or presenting the work.** As of this draft no public disclosure
> has been made (see Q16).

## Contents

| # | Question | # | Question |
|---|----------|---|----------|
| [Q1](#q1-title-of-the-invention) | Title | [Q15](#q15-experiments-conducted--third-party-validation) | Experiments / validation |
| [Q2](#q2-technical-field-of-the-invention) | Technical field | [Q16](#q16-public-disclosure--publication) | Public disclosure |
| [Q3](#q3-search-terms) | Search terms | [Q17](#q17-stage--level-of-development) | Stage of development |
| [Q4](#q4-background-of-the-invention-present-state-of-the-art) | Background | [Q18](#q18-aspects-to-claim--monopolise-proposed-claims) | Proposed claims |
| [Q5](#q5-prior-art) | Prior art | [Q19](#q19-novelty--inventiveness-search-done) | Search done? |
| [Q6](#q6-has-the-work-filled-a-major-gap-in-the-prior-art) | Gap in prior art | [Q20](#q20-would-a-person-of-ordinary-skill-have-arrived-at-this) | Obviousness |
| [Q7](#q7-components-of-the-invention) | Components | [Q21](#q21-broad-workable-ranges-for-the-parameters) | Parameter ranges |
| [Q8](#q8-how-the-invention-works) | How it works | [Q22](#q22-commercialisation-data) | Commercialisation |
| [Q9](#q9-novelty--inventive-step) | Novelty | [Q23](#q23-market-potential--size--trends) | Market |
| [Q10](#q10-advantages--improvements-over-existing-methods) | Advantages | [Q24](#q24-inventors) | Inventors |
| [Q11](#q11-alternative-embodiments--variants) | Variants | [Q25](#q25-user-information) | User information |
| [Q12](#q12-cad-images--line-diagrams-of-the-final-prototype) | Drawings | [Q26](#q26-technology-readiness-level) | TRL |
| [Q13](#q13-inventors-description-of-the-drawings) | Drawing description | [Q27](#q27-additional-notes--remarks) | Additional notes |
| [Q14](#q14-complete-description-incl-working-example--methodology) | Complete description | — | [Open items checklist](#open-items-checklist) |

---

## Q1. Title of the Invention

*Working titles — pick one with the agent:*

- "Toolhead-Actuated System and Method for In-Situ Insertion of Discrete Magnets
  into Parts During Fused-Filament 3D Printing"
- "Host-Controlled Add-On for Automated Embedding of Permanent Magnets in 3D Prints
  Without Printer Firmware Modification"

## Q2. Technical Field of the Invention

*(Problem + solution statement and general purpose.)*

**Field.** Additive manufacturing (fused-filament fabrication, FFF, "3D printing");
specifically, automated insertion of discrete rigid components — here, permanent
magnets — into a part *while it is still being printed*, so that subsequent layers
seal the component inside.

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
operator-confirm → resume sequence, and continues the print. Before any of those
moves is sent, the host checks them against the machine limits **and against the
part printed so far** (derived from the toolpath it is streaming), and refuses
the insert, print left paused, if the nozzle would touch the plate or the part.

**Purpose.** Make embedded-magnet FFF parts producible with far less operator
effort and far better repeatability and polarity control, on inexpensive
off-the-shelf printers, with **no firmware changes** and with G-code that is still
valid for normal printing.

## Q3. Search Terms

in-situ component embedding FFF; automated insert 3D printing; pause-and-insert
additive manufacturing; embedding permanent magnets 3D print; magnet insertion
fused filament fabrication; toolhead pick and place 3D printer; clip-on applicator
3D printer; G-code comment sentinel pause; host-controlled print pause insert;
magnetic holding pole dispenser; shear release placement; insert moulding vs 3D
printing embedding; multi-material toolchanger embedding; nut / heat-set insert
during print; robotic magnet pick and place; Marlin host action pause; polarity
controlled magnet placement; toolpath-derived collision check; tool offset
transform single-tool printer.

## Q4. Background of the Invention (present state of the art)

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
- Fibre systems: do not address discrete magnets/nuts/etc.; proprietary hardware.

## Q5. Prior Art

*(Products, processes, patents, publications. Non-exhaustive — a formal patent
search must be run by the K&K agent, see Q19. Full notes and links in
`project/RESEARCH.md`.)*

**Closest published work — automated in-situ placement (must be cited)**

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

**Host-side pause / marker mechanics**

- **OctoPrint `@` commands** — `@pause` etc. placed in the G-code are never sent to
  the printer; they trigger host functions. (Our `;MAGNET_INSERT` comment is the
  same idea, made SD-safe and carrying parameters.)
- **OctoPrint-GCodeSystemCommands** plugin — map a G-code to a shell/Python action
  (people drive a servo for nozzle cleaning this way).
- **Klipper** `PAUSE`/`RESUME` macros with `SET_GCODE_VARIABLE` state save/restore;
  **Marlin** `M125` / `PARK_HEAD_ON_PAUSE` / `M600` (firmware-side park & restore).
- Slicer "Pause at height" / `M601` (Cura, PrusaSlicer, Creality Print) — the manual
  pause-and-insert method.

**Other**

- Open-hardware tool-changers (Jubilee; E3D tool-changer) — tool-offset handling,
  multiple toolheads on one motion system.
- DIY pick-and-place (3DPlacer, Micro_PNP, Picktor, LumenPnP, OpenPnP) — vacuum
  pickup, feeders, rotation, bottom vision.
- 3D-printer host software (Printrun/Pronterface, OctoPrint) — host-controlled
  G-code streaming, pausing, emergency stop, and a G-code viewer that shows
  print progress from the lines already sent.
- Maker/vendor guides on embedding hardware (Markforged; MLC-CAD; forums) — the
  pocket + pause + seal concept, pocket oversize ~0.1–0.3 mm, 2–3 cap layers.

`[AGENT]` — **patent** search (Espacenet / Google Patents / Indian Patent Advanced
Search / WIPO PATENTSCOPE) for: automated insertion during additive manufacturing;
magnetic component placement heads; marker/sentinel-driven print interruption;
in-situ component embedding; toolpath-derived collision avoidance for an offset
tool.

## Q6. Has the work filled a major gap in the prior art?

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
transform with a damage guard that knows the shape of the part printed so far,
since the firmware is untouched and cannot protect the part itself.

## Q7. Components of the Invention

*(External and internal parts / blocks / sub-systems / process steps.)*

**A. External / physical**

| Ref | Component | Notes |
|-----|-----------|-------|
| A1 | **Clip-on applicator body** | Mounts to the existing print carriage; assumed not to interfere with normal printing (removable clip). |
| A2 | **Magnet magazine** | Holds a stack/column of identical magnets; includes an **escapement** that isolates exactly one magnet against magnet-to-magnet attraction. `[INVENTORS TO COMPLETE — design in progress]` |
| A3 | **Servo actuator** | One hobby servo; the only powered motion the add-on has. |
| A4 | **Magnetic holding pole** | A small pole / pole-piece at the applicator tip that retains one dispensed magnet by magnetic attraction and **fixes its polarity/orientation** (all magazine magnets load the same way). |
| A5 | **Arduino Uno microcontroller** | Drives A3; USB serial to the host; idle watchdog safes the servo. |
| A6 | **Separate 5–6 V servo power supply** | Common ground with A5. |
| A7 | **Standard FFF printer** | Creality Ender-3 V3 SE, unmodified stock firmware, USB-C serial at 115200 baud. |
| A8 | **Host computer** | Windows PC running the control software. |
| A9 / A10 | **The printed part** with a **magnet pocket** | Pocket slightly oversized, optionally with a retention undercut / adhesive, positioned within the offset-reachable area of the bed, covered by "cap" layers after insertion. |

**B. Internal / software blocks** (all running on A8 unless stated)

| Ref | Block | What it does |
|-----|-------|--------------|
| B1 | **G-code post-processor** | Inserts the sentinel comment `;MAGNET_INSERT X Y Z S<dir>` into a sliced file at the chosen layer (Cura / Creality Print `;LAYER:` and PrusaSlicer `;LAYER_CHANGE` markers understood). |
| B2 | **Streaming runner** | Sends G-code line by line, waits for `ok`, detects the sentinel, pauses by withholding lines. Optionally (B15) streams with line numbers and checksums. |
| B3 | **Sentinel parser** | Extracts pocket X/Y, seat height Z, shear direction from the comment. |
| B4 | **Tool-offset transform + damage guard** | Converts pocket coordinates to carriage targets using the measured pole-to-nozzle offset; refuses, with a plain-language reason and the print left safely paused, (1) a pocket off the bed, (2) a nozzle target outside the machine limits, (3) a press into the build plate, and (4) a press or shear that would put the nozzle inside the **part printed so far** — the footprint is built from only the toolpath layers already streamed when the sentinel fires, grown by a configurable margin, tested against a configurable nozzle clearance. One function; used by B5, B10 and the preview alike. |
| B5 | **Insert sequence state machine** | SAVE → PARK → DISPENSE → APPROACH → PRESS → SHEAR → LIFT → ASK(operator) → RESUME; each phase gated by `M400`; never homes mid-print; reports each phase and its exact target to B7 as it starts. |
| B6 | **Dispenser link** | Serial protocol to A5 (`PING` / `DISPENSE` / `RESET` / `STATUS`); rides out the Uno's auto-reset on connect. |
| B7 | **Operator interface** | Tkinter panel: connect/disconnect, load, run, pause/resume, cancel; the Success / Retry / Abort prompt; jog, home, bed-mesh levelling, Z-offset calibration, temperature control (allowed mid-print), raw G-code; a live-print view (current layer in 2D and an isometric 3D view) whose nozzle marker is derived from the lines already streamed against the parsed toolpath — no extra printer traffic — and which, during an insert, follows the phase targets reported by B5. |
| B8 | **Simulation layer** | Software twins of A7 and A5 with identical interfaces and error types, so the whole stack is exercised without hardware. |
| B9 | **Arduino firmware** (on A5) | Receives `DISPENSE`, cycles the servo through one escapement stroke, reports `OK` / `ERR`; idle watchdog safes the servo. `[INVENTORS TO COMPLETE — not yet written]` |
| B10 | **Insert planner + preview** | A dialog in which the operator enters the pocket position, seat height, release direction and target layer; it computes the carriage moves from the *same* geometry function B5 executes, draws the planned nozzle and pole paths over the sliced part (plan view and side view, plus an animated play/scrub view), runs the B4 check live as the fields change, and writes the sentinel into a copy of the file. "What is previewed is what runs" — the preview cannot drift from the executed motion. |
| B11 | **Firmware-pause substitution** | B2 recognises the slicer/firmware pause codes (`M0`, `M1`, `M25`, `M600`, `M601`) and withholds them, because the host owns the pause and B5 does the parking. B1 can optionally write a real `M0` next to the sentinel, so a single file both pauses correctly when printed from the SD card (manual insert) and streams cleanly through the host (automated insert). |
| B12 | **Emergency stop** | One always-enabled control that cancels streaming, releases any operator prompt B5 is waiting on, and writes `M112` straight to the printer without waiting for the normal acknowledgement; the operator then power-cycles / `M999` and reconnects. |
| B13 | **Safe cancel** | Cancelling a run stops streaming, waits for the worker to actually stop, then retracts, lifts clear, parks and (configurable) turns the heaters off — skipped, with a log line, if B5 still owns the printer. |
| B14 | **Run transcript** | One timestamped log per streamed job with a summary block (duration, lines sent, sentinels seen, errors, final position and temperatures) — the record of every insert attempt. |
| B15 | **Streaming reliability (opt-in)** | Line-numbered, checksummed transmission with a 64-line resend buffer replayed on a firmware `Resend:`; optional re-send of `M420 S1` after any `G28` so bed-mesh compensation survives the print's own homing. Off by default until bench-tested. |

## Q8. How the Invention works

*(Working, processes, and interaction between components.)*

1. The part is designed with a magnet pocket ending a few layers below its top
   surface; it is sliced normally.
2. **B1** (or the planner **B10**) inserts one `;MAGNET_INSERT X Y Z S<dir>` comment
   at the layer where the pocket is complete. The file is still SD-printable (the
   printer ignores comments).
3. The host (**B2**) streams the file to the printer, one line per `ok`. The
   operator panel (**B7**) shows the nozzle position and current layer inferred
   from the lines sent so far, without polling the printer.
4. On seeing the sentinel, **B2** stops sending lines (the printer holds position
   and temperature) and calls **B5** with the parsed values from **B3**.
5. **B4** computes the carriage target = pocket − offset and the press depth =
   seat_z − offset_z, and checks every target before anything moves: reachable
   within the machine limits; press not below the build plate; and — using the
   toolpath being streamed, restricted to the layers already printed at that
   moment — the nozzle not inside the part during PRESS or at any of ten sampled
   points along SHEAR while below the printed top plus a clearance. If any check
   fails the insert aborts with the reason and the print stays paused. The
   planner (**B10**) runs the identical function and reports each reason in
   plain language before the file is even saved.
6. **B5** runs, reporting each phase and its target to **B7** as it starts:
   - **SAVE** the current position, filament counter, coordinate/extruder modes,
     feedrate, temperatures.
   - **PARK**: retract filament; lift Z to a safe clearance; set the nozzle to a
     cooler standby temperature.
   - **DISPENSE**: host sends `DISPENSE` to **B6 → A5**; the servo (**A3**) cycles
     the escapement (**A2**) so one magnet transfers onto the holding pole
     (**A4**), which fixes its polarity. (During early development a human loads
     the magnet on an operator prompt.)
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
9. **If something goes wrong.** A dispenser error, a serial error, or an
   out-of-envelope target leaves the print paused and resumable with the nozzle
   temperature restored (an operator abort turns the nozzle off). Cancelling a
   run (**B13**) retracts, lifts, parks and cools the machine once the stream has
   actually stopped. The emergency stop (**B12**) halts the firmware immediately,
   even while the sequence is waiting on the operator. Every run is recorded by
   **B14**.

## Q9. Novelty / Inventive Step

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
7. **Collision-aware placement check using the part's own toolpath, limited to
   what has been printed.** Because the pole is offset from the nozzle, seating
   the magnet puts the *nozzle* at a different XY and, with a pole tip above the
   nozzle, *below* the seat height. The host derives the footprint of the
   partly-printed part from the sliced G-code it is already streaming — counting
   only the layers printed at the moment the marker fires, since later layers do
   not yet exist as material — and refuses any PRESS or SHEAR whose nozzle
   position would lie inside that footprint while below the printed top plus a
   clearance. A bed-limit check alone cannot catch this; the toolpath-derived,
   printed-so-far check is specific to single-tool, offset-tool insertion.
8. **Pause-code substitution for one dual-use file.** The host withholds
   firmware pause codes and runs its own park/insert/resume routine in their
   place, so a file carrying both a conventional pause and the sentinel prints
   correctly from the SD card (operator inserts by hand) *and* through the host
   (automated insert) without re-slicing.
9. **Preview-equals-execution planning.** The operator-facing planner draws and
   envelope-checks the identical geometry the run executes (one shared
   function), so the previewed motion is the commanded motion by construction;
   during the run the same targets are reported back to the operator display as
   each phase starts.

*Not claimed as novel* (standard host features, listed in Q7 for completeness):
emergency stop, safe cancel, run logging, line-numbered streaming, and the
progress-derived live view — OctoPrint and Printrun have equivalents.

## Q10. Advantages / improvements over existing methods

*(Against the closest patent and non-patent documents — see Q5, Q19.)*

- Removes the operator from the per-insert loop → **less labour, more repeatable**.
- **Polarity is guaranteed**, not operator-dependent.
- **No dedicated placement actuator** → cheaper, lighter add-on (one servo).
- **No firmware or slicer modification**; sliced file still prints from SD.
- Works on **low-cost single-tool printers**, not just tool-changers.
- **Damage guard + no mid-print homing + full state restore** → lower risk of
  crashes / ruined prints than ad-hoc manual resumes. The guard understands the
  part printed so far, so it neither drives the nozzle into existing material
  nor needlessly refuses a pocket because of layers that do not exist yet.
- **Host-side safety layer** independent of firmware features: emergency stop
  that also releases a pending operator prompt, safe cancel that parks and cools,
  a transcript of every run.
- Standby-temp + retract handling reduces **ooze / layer-shift** artefacts common
  to long manual pauses.
- Scales toward **multiple inserts per part** (multiple sentinels) and, later,
  unattended operation.
- `[VERIFY against the closest patents once the search is done.]`

## Q11. Alternative embodiments / variants

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
- **Collision-check variants**: bounding box of the printed layers (baseline);
  exact per-layer polygon occupancy of the printed lines; a model of the
  applicator body's lowest point in addition to the nozzle tip; a check that
  also covers the return travel on RESUME.
- **Control variants**: fully automated confirmation via a hall-effect / vision
  check of the pole instead of an operator prompt; migration to Klipper macros;
  Raspberry Pi host; networked/headless operation.
- **Printer variants**: any FFF printer with USB/serial G-code; CoreXY; bed-slinger;
  tool-changer carrying this as one tool.
- **Magnet variants**: different grades/sizes; high-temp grades where cap-layer
  reheat risks demagnetisation; pre-magnetised arrays.

## Q12. CAD images / line diagrams of the final prototype

*(Two sets: one fully labelled, one unlabelled; include flow charts.)*

`[INVENTORS TO COMPLETE]` — the mechanical drawings are not yet available (the
prototype is not built). Required:

- Applicator assembly (magazine, escapement, servo, holding pole) mounted on the
  print carriage — one **fully labelled** set, one **unlabelled** set.
- Section view of a magnet seated in a printed pocket with cap layers.
- **Flow chart** of the insert state machine (SAVE → … → RESUME) — can be drawn
  from `project/PROJECT_PLAN.md` §4 / `project/HOW_IT_WORKS.md` §6.
- Diagram of the tool-offset geometry (nozzle vs pole, carriage target = pocket −
  offset).
- System block diagram (PC ↔ printer ↔ Arduino ↔ servo) — see
  `project/HOW_IT_WORKS.md` §2.

**Already producible from the software** (no CAD needed): the planner's plan-view
(X–Y) and side-view (X–Z) figures of the phase-coloured nozzle path, the dashed
pole path and the pocket over the sliced part, and the isometric 3D toolpath view
with the insert waypoints — `python main.py --preview <file.magnet.gcode>` and the
panel's live view render them with matplotlib and can be saved as images. These
make good "method" drawings alongside the mechanical ones.

## Q13. Inventor's description of the drawings

`[INVENTORS TO COMPLETE once drawings exist.]` Base narrative available in
`project/HOW_IT_WORKS.md` (plain language) and `.CLAUDE/CLAUDE.md` (technical).

## Q14. Complete description incl. working example / methodology

See Q7 (components) and Q8 (operation). Worked example (simulation, current
build):

**Set-up**

- Part: test coupon, magnet pocket centred at bed (60, 60), pocket floor such that
  seat height Z = 6 mm, cap = 4 layers.
- Sentinel injected at the layer covering the pocket:
  `;MAGNET_INSERT X60 Y60 Z6 S+X`.
- Measured tool offset (example): (30, 0, 5) mm (pole 30 mm +X of nozzle, tip 5 mm
  above nozzle tip).
- Host computes: carriage approach = (30, 60); press nozzle Z = 6 − 5 = 1 mm;
  shear target = (35, 60). All within the 220 × 220 × 250 mm envelope; the nozzle
  at X30 lies outside the coupon's printed footprint (X 40..80) → proceed.

**Commands sent, phase by phase** — exactly what the current implementation
sends; `saved.*` are the values captured at SAVE; the print position here is
(60, 60, 6) with the nozzle target 200 °C:

| Phase | Commands sent to the printer | Purpose |
|-------|------------------------------|---------|
| SAVE | `M400`, `M114` (read back) | Record X Y Z E, feedrate, G90/G91, M82/M83, temperatures |
| PARK | `M83` · `G1 E-3 F2400` · `G90` · `G1 Z21 F6000` · `M400` · `M104 S160` | Relative extrusion; retract 3 mm; lift to safe Z (saved Z + 15); wait; nozzle to standby |
| DISPENSE | `DISPENSE` → Uno (or operator prompt) | One magnet onto the holding pole |
| APPROACH | `G90` · `G1 X30 Y60 F6000` · `M400` | Carriage to pocket − offset; pole now over the pocket |
| PRESS | `G1 Z1 F60` · `G4 P500` · `M400` | Slow Z press to seat_z − offset_z; dwell 0.5 s; wait |
| SHEAR | `G1 X35 Y60 F1200` · `M400` | 5 mm lateral move in +X; pole slides off the seated magnet |
| LIFT | `G1 Z21 F6000` · `G1 X5 Y5 F6000` · `M400` | Clear the part; move to the park corner |
| ASK | operator prompt → success / retry / abort | Retry re-enters at DISPENSE (`RESET` sent to the Uno first), up to 3 times |
| RESUME | `M104 S200` · `M109 S200` · `G90` · `G1 Z21 F6000` · `G1 X60 Y60 F6000` · `M400` · `G1 Z6 F6000` · `M400` · `M83` · `G1 E2 F300` · `G92 E<saved E>` · `M82`/`M83` · `G90`/`G91` · `G1 F<saved feed>` | Reheat and wait; return at safe Z, then descend; un-retract/prime; restore the E reference and every modal state |

No `G28` appears anywhere; every phase ends with `M400` so the host acts only on
completed motion. On any error the nozzle target is restored (or set to 0 on an
operator abort) and the print is left paused and resumable. Each phase name and
its target are also reported to the operator display the moment that phase
starts.

**Outcome.** Print resumes; cap layers seal the magnet.

**Validation of this example**

- Verified end-to-end against a simulated printer + simulated dispenser; **262
  automated tests** pass, including a full-workflow test (slice → plan → save →
  stream → sentinel → insert → resume → end of file), the out-of-envelope abort
  path, the nozzle-into-part refusal, the retry and abort paths, the emergency
  stop mid-run, the safe-cancel retreat, and the line-numbered streaming resend.
- The **printer serial link has run on the real machine** (Ender-3 V3 SE over
  USB, 2026-09-09) and a real sliced part was streamed through the host on
  2026-09-15 — no magnet insert on hardware yet.

**Notes on the collision check in this example**

- With the baseline offset the nozzle presses at X30 Y60 Z1. For a coupon whose
  *printed* footprint spans X 40..80 that point is clear of the part and the plan
  is accepted; for a coupon spanning X 0..80 it lies *inside* the part and the
  toolpath collision check (Q9 item 7) refuses the plan with the reason — the
  pocket must sit within 30 mm of the part's −X edge for a pole-above-nozzle
  applicator, or a deployable pole is needed (Q11).
- The footprint counts only layers printed by the time the sentinel fires. A
  coupon that is 40..80 wide up to the insert layer but flares to 0..80 in the
  cap layers above it is therefore accepted — the wider material does not exist
  yet when the press happens. This is always a subset of the whole-file
  footprint, so the refinement can only stop refusing geometry that is not yet
  printed; it never accepts a press into material that is.

Broad workable parameter ranges: see Q21.

## Q15. Experiments conducted / third-party validation

**No magnet insert on hardware yet.** Validation so far:

- **Software simulation** — `SimPrinter` / `SimDispenser`, **262 `pytest` cases**
  covering the parser, post-processor, streaming runner (plain and line-numbered,
  resend replay, firmware-pause skipping), every branch of the insert state
  machine (happy path, out-of-range, nozzle-into-part, retry, abort, dispenser
  failure, mode restore, phase reporting), the planner geometry and the
  printed-so-far footprint, the UI mediator (emergency stop, safe cancel,
  background one-off commands, connect/disconnect), the run log, and the serial
  links driven by a fake port. The Tkinter windows themselves are exercised by
  hand through the real Tk event loop, not by automated tests.
- **Real printer, serial control** — 2026-09-09: the host connected to the
  Ender-3 V3 SE over USB, completed the `M115` handshake and read position via
  `M400`/`M114`. 2026-09-15: a real sliced part (46 layers, PETG) was streamed
  through the host and printed; jog, home, temperature control and bed levelling
  were exercised from the panel. This confirms the streaming/flow-control layer
  on stock firmware; the sentinel path was not exercised on hardware. No further
  hardware sessions between 2026-09-15 and this draft.
- **Not yet done** (`project/PROJECT_PLAN.md` §5): applicator build; servo-alone
  test; cold "air-insert" of APPROACH/PRESS/SHEAR/LIFT; magnet-near-bed
  attraction; nozzle idle-timeout; first coupon with a real magnet; bench test of
  the emergency stop (`M112`) against the stock firmware; bench test of the
  Z-offset calibration and of line-numbered streaming.
  `[INVENTORS TO COMPLETE — fill in results as they happen.]`
- No third-party validation.

## Q16. Public disclosure / publication

**None as of this draft.** The project exists in a git repository on the
inventors' machine with a remote at
`github.com/KL-Mithunvel/Creality-Ender-3-V3-SE-`, which the owner confirmed on
2026-09-16 is **private** (not publicly visible); no change is known as of
2026-09-18 `[VERIFY — owner to re-confirm at submission]`. **No** paper, poster,
video, demo, sale, or public repo. `[If this changes, record the date and forum
here and tell the K&K agent immediately — it affects filing deadlines and foreign
rights. Keep the repository private until the agent clears publication.]`

## Q17. Stage / level of development

**Early, with the control software complete.** Concept fully formulated and
specified; the host software (streaming, sentinel, insert state machine with a
toolpath-aware damage guard, planner/preview, control panel with a live insert
view, emergency stop and safe cancel, run logging, calibration aids) is
**complete for the operator-assisted phase and validated in simulation** through
software chunk C31; the printer control layer is **validated on the real printer**
(serial control and a real print streamed through the host). The mechanism
(magazine / escapement / holding pole / mount) is designed on paper, **not
built**; the Arduino sketch is not written; **no magnet insert has been performed
on hardware**.
→ Between "basic conceptualisation" and "experimental proof of concept". (See
Q26 — TRL 3, partial.)

## Q18. Aspects to claim / monopolise (proposed claims)

*(Indicative directions only — for the agent to draft.)*

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
   local height of the partly-printed part from the portion of the toolpath
   already streamed when the marker is reached** — counting only layers that
   exist as material at that moment — and rejects any press or release move
   that would place the printer's own nozzle (or applicator body) inside that
   part while below the printed top plus a clearance.
8. The method where the host **withholds firmware pause commands** present in
   the toolpath and performs its own pause/insert/resume in their place, such
   that one toolpath file supports both manual insertion when printed
   standalone and automated insertion when streamed.
9. The method where the operator-facing planning step **computes, displays and
   checks the placement motion with the same function that later commands
   it**, writes the marker into the toolpath, and during execution reports each
   phase's commanded target back to the operator display from the same values.
10. The apparatus of claim 6 where the holding feature is **deployable** between
    a retracted position clear of normal printing and a deployed position below
    the nozzle tip, actuated by the same dispenser actuator, by a passive
    engagement the printer's motion performs, or by a second actuator.
11. Dependent claims: escapement isolating one magnet against mutual attraction;
    standby-temperature and retract handling during the pause; operator
    confirm/retry loop with dispenser reset; multi-marker / multi-insert;
    adhesive-assisted retention; passive stripper variant; non-magnet
    components; pocket positioned within the offset distance of a part edge;
    footprint as a bounding box or as exact per-layer occupancy of the printed
    lines; the check sampling multiple points along the release move; an
    emergency stop that also releases a pending operator prompt before halting
    the firmware.

## Q19. Novelty / inventiveness search done?

*(Databases / references used and results.)*

Informal web/literature review is done — see **`project/RESEARCH.md`** (academic
papers, OctoPNP, host-control docs, maker practice) and the notes in Q5. It found
the IEEE 2021 / OctoPNP line of work as the closest published art. **No formal
patent-database search has been done** (Espacenet / Google Patents / Indian Patent
Advanced Search / WIPO PATENTSCOPE) — the K&K agent should run it. Table to fill:

| S.no | Reference | Existing idea | Our invention |
|------|-----------|---------------|---------------|
| 1 | IEEE 2021 "Automated In-Situ Placing…" / OctoPNP | automated in-situ placement via a **powered electromagnet gripper + rotary stepper + 2 cameras + custom slicer + OctoPrint plugin** on a modified Prusa | **no placement actuator** (servo only feeds); **printer motion** does press + **lateral shear** release; **no vision**; **inert comment** marker; **stock firmware**; single operator confirm; damage guard from the printed-so-far toolpath |
| 2 | manual pause-and-insert guides (Markforged, forums) | operator hand-places a component during a slicer pause | automated dispense; polarity fixed by the holding pole; no operator per insert |
| 3 | OctoPrint `@pause` / GCodeSystemCommands | in-stream marker triggers a host action / external script | same mechanism, but a **`;` comment** (SD-safe) carrying **placement coordinates**, driving a full park → place → shear → resume routine |
| 4 | tool-changer projects (Jubilee, E3D) | multiple toolheads on one motion system, often needs firmware support | one **passive** feeder tool; placement by existing motion; no firmware change |
| 5 | OctoPrint / Printrun hosts | emergency stop, cancel, G-code viewer driven from sent lines | not claimed (Q9); reused as the safety and display layer around the insert |
| 6 | `[AGENT — patent search results]` | | |

## Q20. Would a person of ordinary skill have arrived at this?

Proposed answer: **No — not obviously.** Reasons to develop with the agent: the
prior art points toward *either* keeping a human in the loop *or* adding a
dedicated placement actuator / special printer; the specific combination —
inert-comment marker + host flow-control pause + **re-using the print motion for
both press and a lateral shear-release keyed to pocket geometry** + single-servo
feeder + no-homing state-restoring resume + a damage guard that reads the part's
own toolpath because the untouched firmware cannot protect the part — is a
non-obvious way to get automated, repeatable, polarity-correct insertion on a
stock single-tool printer. `[INVENTORS TO COMPLETE — add your own reasoning;
AGENT to test against the search.]`

## Q21. Broad workable ranges for the parameters

*(Design intent / simulation defaults from `magnet_embed/config.yaml`; confirm on
hardware.)*

**Mechanical / part**

| Parameter | Working range (indicative) | Current default |
|-----------|----------------------------|-----------------|
| Magnet diameter | 3–15 mm | `[TBD]` |
| Magnet thickness | 1–5 mm | `[TBD]` |
| Pocket clearance (per side) | +0.05 to +0.30 mm | `[TBD]` |
| Cap layers over magnet | 2–8 | `[TBD]` |
| Tool offset X/Y (pole tip − nozzle tip) | any, subject to the reachable envelope; the reachable pole area is the bed minus a border of the offset on two sides | 30 / 0 mm |
| Tool offset Z (**+ = pole above nozzle**) | −10 to +15 mm. Positive: pocket must be within the X/Y offset of a part edge or a deployable pole is used (Q11). Negative: any pocket reachable, pole must deploy/retract. | +5 mm |
| Build volume (this printer) | 220 × 220 × 250 mm | — |

**Insert motion**

| Parameter | Working range (indicative) | Current default |
|-----------|----------------------------|-----------------|
| Safe Z lift before travel (above the paused print height) | 5–30 mm; must clear the applicator body over the tallest printed feature | 15 mm |
| Park position (nozzle, while the operator works) | any clear bed corner | X5 Y5 |
| Travel feed (park, approach, resume) | 1500–9000 mm/min | 6000 mm/min |
| Retract before pause | 1–6 mm @ 1200–3000 mm/min | 3 mm @ 2400 |
| Prime on resume (un-retract + a touch extra) | 1–6 mm @ 100–600 mm/min | 2 mm @ 300 |
| Standby nozzle temp during pause | (soften point) to (print − 20 °C), or fully off | 160 °C |
| Press feed (Z into pocket) | 20–120 mm/min; press is **open-loop** (commanded depth, no force sensing) | 60 mm/min |
| Press over-travel below the nominal seat (proposed parameter) | 0–0.3 mm | not yet implemented |
| Press dwell | 100–1000 ms | 500 ms |
| Shear distance | 2–10 mm | 5 mm |
| Shear feed | 300–3000 mm/min | 1200 mm/min |
| Operator retries before abort | 0–5 | 3 |

**Damage guard**

| Parameter | Working range (indicative) | Current default |
|-----------|----------------------------|-----------------|
| Nozzle clearance above the printed top while over the part | 0.5–3 mm; add the applicator body's overhang below the nozzle tip if it hangs lower | 1.0 mm |
| Footprint margin grown around the printed part | 0–5 mm | 2.0 mm |
| Sample points along the shear move | 4–20 | 10 |

**Communication**

| Parameter | Working range (indicative) | Current default |
|-----------|----------------------------|-----------------|
| Serial baud (printer) | 115200 (this printer) | 115200 |
| Acknowledgement timeout (no `ok` / `busy` / `wait`) | 10–120 s; must exceed the longest firmware operation between keepalives | 30 s |
| Resend buffer (line-numbered mode, opt-in) | 16–256 lines | 64 lines |
| Dispenser reset settle after opening the port | 1.5–4 s | 2.5 s |

## Q22. Commercialisation data

*(2–5 companies with full addresses + a short marketing profile.)*

`[INVENTORS TO COMPLETE / AGENT — names + full addresses of companies who might
manufacture / licence this.]` Categories to consider: desktop 3D-printer OEMs;
3D-printer accessory/upgrade makers; automation-integration firms; magnet
suppliers with assembly services; contract manufacturers doing embedded-electronics
prints. **Do not list companies without checking** — this section must be real.

1. `[company + address]`
2. `[company + address]`
3. `[company + address]`
4. `[company + address]`
5. `[company + address]`

Short marketing profile: `[INVENTORS TO COMPLETE]` — one paragraph: the add-on
turns a sub-$300 printer into a machine that produces embedded-magnet parts
hands-free, with guaranteed polarity, no firmware voiding, at a fraction of a
tool-changer's cost.

## Q23. Market potential / size / trends

`[INVENTORS TO COMPLETE / AGENT — with cited sources; do not invent figures.]`

| Year | Estimated market size | Growth drivers | Notable existing devices |
|------|----------------------|----------------|--------------------------|
| | `[cite a source]` | desktop FFF adoption; demand for functional/assembled prints; magnet use in enclosures, jigs, toys, medical models | tool-changer printers; manual pause-insert workflow |

## Q24. Inventors

1. kl mithunvel — `<klm@smtw.in>` — `[INVENTORS TO COMPLETE — full legal name,
   address, nationality]`
2. `[INVENTORS TO COMPLETE — second inventor's full legal name, email, address,
   nationality]`
3. `[INVENTORS TO COMPLETE — teacher / guide: confirm with them whether they are
   an inventor (made an inventive contribution) or only a facilitator.
   Institutions often have IP assignment rules — check the college's policy
   before filing.]`

## Q25. User Information

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
  setup; vs. manual labour, it removes operator minutes per insert.
  `[INVENTORS TO COMPLETE — quantify once the BOM is fixed]`

## Q26. Technology Readiness Level

**TRL 3 (partial).** TRL 2 (technology concept formulated) is met; TRL 3
(experimental proof of concept) is **partially** met — the control method is
proven in software simulation, and the host-to-printer control layer (stock
firmware, no modification) is proven on the real printer including a complete
streamed print. The insertion mechanism itself has not been built or tested.
Not yet TRL 4 (lab validation of the whole system).
→ Tick **TRL 2** and **TRL 3** (partial), Research phase.

## Q27. Additional notes / remarks

- The host software is complete for the operator-assisted phase
  (`project/BUILD_PLAN.md`, chunks C1–C31): config, simulated + real
  printer/dispenser links, sentinel parser + post-processor, streaming runner
  with firmware-pause substitution and opt-in line-numbered resend, the full
  park → dispense → press → shear → resume insert state machine with per-phase
  reporting, a shared insert-geometry module carrying the damage guard, the
  insert planner with live preview and animated motion, a Tkinter control panel
  with a live print view that follows the insert, emergency stop, safe cancel,
  bed-levelling and Z-offset calibration aids, and per-run logging — **262
  automated tests**. The printer control layer has been exercised on the real
  Ender-3 V3 SE (serial handshake 2026-09-09; a full real print streamed
  2026-09-15). The physical mechanism (magazine / escapement / holding pole /
  mount) and the Arduino sketch are **not yet built**; no magnet insert has
  been performed on hardware.
- Known design issue recorded 2026-09-16 and reflected in Q8/Q9/Q11/Q18/Q21:
  with the pole tip above the nozzle, the nozzle can be driven into the printed
  part during PRESS unless the pocket is near a part edge. The toolpath-derived
  collision check is implemented in the host (planner, preview and run share it)
  and, since 2026-09-16 (C30), counts only the layers printed at insert time;
  the deployable-pole embodiment remains a design option. Both are disclosed so
  they are covered regardless of which the prototype adopts. Remaining limits of
  the guard, also disclosed as variants in Q11: the footprint is a bounding box
  of the printed layers (an L-shaped printed cross-section is treated as its
  enclosing rectangle — conservative), and the applicator body itself is not
  modelled, only the nozzle tip.
- Unverified on the stock firmware, to be bench-tested before the claims rely
  on them: whether `M112` is honoured mid-move (`EMERGENCY_PARSER`), the
  line-number/checksum resend format, and `M851`/`M500` for the Z-offset
  calibration. None of these affects the core method (Q9 items 1–9).
- Reference material and prior-art notes: **`project/RESEARCH.md`** (comprehensive)
  and `project/BUILD_PLAN.md` → References (protocol-focused).
- **Before any public disclosure or repo publication, consult the K&K agent** (see
  the warning at the top).
- Confirm **college IP-ownership policy** and the teacher's role before filing.

---

## Open items checklist

Every placeholder in this draft, gathered in one place. Tick as they are resolved.

**Inventors**

- [ ] Q7 A2 / B9 — magazine escapement design; Arduino sketch (after the build)
- [ ] Q12 — labelled + unlabelled applicator drawings, pocket section view, flow
      chart, offset diagram, block diagram (software figures can be exported now)
- [ ] Q13 — description of the drawings
- [ ] Q15 — hardware results as they happen (air-insert, first coupon, `M112`,
      Z-cal, line-numbered streaming)
- [ ] Q16 — re-confirm the repository is still private at submission
- [ ] Q20 — inventors' own reasoning on non-obviousness
- [ ] Q21 — magnet size, pocket clearance, cap layers, measured offset (`[TBD]`)
- [ ] Q22 — 2–5 real companies with addresses; marketing paragraph
- [ ] Q24 — full legal names, addresses, nationalities; teacher's role
- [ ] Q25 d — quantified cost advantage once the BOM is fixed
- [ ] College IP-ownership policy checked

**K&K agent**

- [ ] Q5 / Q19 — formal patent-database search; fill row 6 of the Q19 table
- [ ] Q10 — verify the advantages against the closest patents found
- [ ] Q18 — draft the claims from the directions given
- [ ] Q23 — market data with sources
- [ ] Clearance before any publication or public repository
