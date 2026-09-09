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
   the print still paused.
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
- Sequence executes SAVE→PARK(retract 3 mm, Z-hop +15 mm, nozzle→160 °C)→DISPENSE
  →APPROACH→PRESS(F60, 500 ms dwell)→SHEAR(5 mm @ F1200)→LIFT→ASK→RESUME
  (nozzle→200 °C wait, return to (60, 60, 6), un-retract, `G92 E` restore).
- Print resumes; cap layers seal the magnet.
- Verified end-to-end against a simulated printer + simulated dispenser; 44
  automated tests pass. **No hardware run yet.**

Broad workable parameter ranges: see Q21.

## 15. Experiments conducted / third-party validation

**None on hardware yet.** Current validation is **software simulation only**
(`SimPrinter` / `SimDispenser`, 44 `pytest` cases). Planned bench tests
(`project/PROJECT_PLAN.md` §5): servo-alone; cold "air-insert"; magnet-near-bed
attraction; nozzle idle-timeout; then a first coupon. `[Fill in results as they
happen.]`

## 16. Public disclosure / publication

**None as of this draft.** The project exists only in a **private** git repository
on the inventors' machine. **No** paper, poster, video, demo, sale, or public repo.
`[If this changes, record the date and forum here and tell the K&K agent
immediately — it affects filing deadlines and foreign rights.]`

## 17. Stage / level of development

**Early.** Concept fully formulated and specified; control software for the printer
side partially built and validated **in simulation**; mechanism (magazine/
escapement/pole) designed on paper, **not built**; **no hardware validation**.
→ "Basic conceptualization stage", moving toward experimental proof of concept.
(See Q26 — TRL 2–3.)

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
7. Dependent claims: escapement isolating one magnet against mutual attraction;
   standby-temperature and retract handling during the pause; operator
   confirm/retry loop; multi-marker / multi-insert; adhesive-assisted retention;
   passive stripper variant; non-magnet components.

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
| Tool offset X/Y | any, subject to reachable envelope | 30 / 0 mm |
| Tool offset Z (pole vs nozzle tip) | −5 to +15 mm | +5 mm |
| Safe Z lift before travel | 5–30 mm | 15 mm |
| Retract before pause | 1–6 mm @ 1200–3000 mm/min | 3 mm @ 2400 |
| Standby nozzle temp during pause | (soften pt) to (print − 20 °C), or fully off | 160 °C |
| Press feed (Z into pocket) | 20–120 mm/min | 60 mm/min |
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

**TRL 2–3.** TRL 2 (technology concept formulated) is met; TRL 3 (experimental
proof of concept) is **partially** met — the control method is proven in software
simulation but not yet with hardware. Not yet TRL 4 (lab validation).
→ Tick **TRL 2** and **TRL 3** (partial), Research phase.

## 27. Additional notes / remarks

- The host software is complete for Phase 1 (`project/BUILD_PLAN.md`, chunks C1–C6):
  config, simulated + real printer/dispenser links, sentinel parser + post-processor,
  streaming runner, the full park→dispense→press→shear→resume insert state machine,
  a Tkinter control panel, per-run logging — **94 automated tests**, validated in
  simulation only. The physical mechanism (magazine / escapement / holding pole /
  mount) and the Arduino sketch are **not yet built**; no hardware run has happened.
- Reference material and prior-art notes: **`project/RESEARCH.md`** (comprehensive)
  and `project/BUILD_PLAN.md` → References (protocol-focused).
- **Before any public disclosure or repo publication, consult the K&K agent** (see
  the warning at the top).
- Confirm **college IP-ownership policy** and the teacher's role before filing.
