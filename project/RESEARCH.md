# Research — Prior Art, Similar Projects, and How They Inform This Build

A survey of existing work on automated component insertion during 3D printing,
host-side print control, and the mechanical sub-problems, with notes on what each
source means for **this** project. Compiled 2026-09-09 from web sources (GitHub,
official docs, academic papers, maker forums).

> `project/BUILD_PLAN.md` has the terse, protocol-focused reference list; this file
> is the fuller version. The patent draft (`docs/INVENTION_DISCLOSURE_DRAFT.md`)
> pulls its prior-art section from here and from **`docs/PRIOR_ART_PATENT_SEARCH.md`**
> (informal patent search, 2026-09-18 — closest: the Stratasys embedded-inserts
> family US 8,070,473 B2 / EP 2 231 375 B1). A **formal patent-database search is
> still owed** (that's for the K&K agent); both files are background only.

---

## 1. Closest prior art — the OctoPNP / augmented-slicing line of work

This is the most directly comparable published work and the single most important
thing to be aware of, both for design and for the patent.

### "Automated In-Situ Placing of Metal Components Into 3D Printed FFF Objects" (IEEE, May 2021)

Group around **T. Plätzsch** et al. (the OctoPNP authors).

- **Machine:** a modified **Prusa i3** FFF printer with an **electromagnetic pick-and-place
  gripper** bolted to the back of the X-carriage. The magnet sits on a **hollow-shaft
  NEMA 8 stepper** with wires routed through the shaft and a **slip-ring**, giving
  unlimited gripper rotation.
- **Staging:** a **printed component tray** clipped to the print bed holds the parts
  (nuts, ferromagnetic components) in known positions; the tray layout changes per print.
- **Software:** an **augmented slicer** lets the user drop generic component models from
  a library into the model; it then **auto-generates the cavities and the placement
  G-code** and sends them to the printer.
- **Control:** the pick-and-place unit is driven by the **OctoPNP** OctoPrint plugin,
  which uses a **head camera + bed camera + OpenCV** to measure exact part position and
  rotation before placing.

### OctoPNP (`github.com/platsch/OctoPNP`)

- OctoPrint plugin for **camera-assisted** pick-and-place in 3D printers; grew out of a
  research project on integrated printing of electronics (wires + SMD parts) with FDM.
- Requires: a **grid tray** of part boxes, a **head camera** (find the part on the tray),
  a **bed camera** (align during placing). OpenCV does the vision.
- On tool offsets, the docs say plainly: *"Offsets between tools can be handled by the
  slicer, by OctoPNP or by the printer firmware. Having the firmware manage all offsets
  is generally highly encouraged to avoid frequent G-code generation."*

### Related earlier work

- **"3D-Printable Electronics — Integration of SMD Placement and Wiring into the Slicing
  Process for FDM Fabrication"** (2017) — same group; slicer-integrated SMD placement.
- **"Embedding of SMD populated circuits into FDM printed objects"** (2017).
- **"Towards Integrating 3D Printing and Automated Assembly"** (2023) — broadens the
  component range (gearboxes, embedded sensors, robotic devices).
- **"Printegrated Circuits: Personal Fabrication of 3D Printed Devices with Embedded
  PCBs"** (arXiv 2509.08459, 2025) — recent, embed-PCB angle.

### How this project differs (design + novelty notes)

| Aspect | OctoPNP / IEEE 2021 work | This project |
|--------|-------------------------|--------------|
| Placement actuator | Dedicated **powered electromagnet gripper** + NEMA 8 stepper + slip-ring for rotation | **No dedicated actuator.** One servo just *feeds* a magnet; the **printer's own X/Y/Z motion** does the press and a **lateral shear** release |
| Alignment | Two cameras + OpenCV | **Open-loop** + a single **operator confirm/retry** prompt (a hall sensor is a later option) |
| Part staging | Printed **tray on the bed**, picked per-print | **Magazine on the toolhead** add-on, gravity/escapement fed |
| Slicer | Custom **augmented slicer** generates cavities + G-code | Cavity is designed by the user in normal CAD; a lightweight **post-processor** injects one comment marker into an already-sliced file |
| Tool offset | Prefer **firmware-managed** offsets | Firmware is **unmodified** (stock Creality) → offset transform is done **in the host** (`insert_magnet`), with an envelope check |
| Host | OctoPrint + OctoPNP plugin (+ a Pi) | Standalone Python host, **PC-tethered**, our own streaming loop |
| Release mechanism | Electromagnet switched off | **Lateral shear** using the pocket wall as the reaction feature (passive holding pole) |

The shared ideas — *cavity + pause + place + seal*, and *slicer/host generates the
placement moves* — are **not novel to us**. The candidate novelty is the combination
in the right-hand column: no placement actuator, printer-motion press + lateral
shear-release, inert-comment marker, no firmware change, no vision. (The agent must
test this against a real search — see `docs/INVENTION_DISCLOSURE_DRAFT.md` Q9/Q19.)

---

## 2. Pause / external-trigger mechanics in existing host software

Everything here **validates** our approach — we are reusing well-trodden patterns.

### OctoPrint `@` commands  (official)

- `@pause`, `@resume`, `@cancel` and custom `@`-commands placed **in the G-code stream**
  are *"never sent to the printer but instead trigger functions inside OctoPrint."*
- **This is exactly our sentinel pattern.** We use a `;` **comment** (`;MAGNET_INSERT …`)
  rather than `@` — even more inert (a comment also survives an SD print unchanged),
  and we carry parameters (X/Y/Z/S) on the same line.
- Docs: https://docs.octoprint.org/en/main/features/atcommands.html

### OctoPrint GCodeSystemCommands plugin

- Maps a chosen G-code to a **local shell / Python command** — people use it to poke a
  **servo for nozzle cleaning**, relays, etc., from within a print.
- Same shape as our "sentinel → run a routine that talks to the Arduino."
- `github.com/kantlivelong/OctoPrint-GCodeSystemCommands`

### Klipper `PAUSE` / `RESUME` macros

- `PAUSE` uses `SET_GCODE_VARIABLE` to **save state** (z-hop amount, hotend temp) for
  `RESUME`; parks the toolhead at a safe point (e.g. centre-X, front-Y); integrates with
  slicer-inserted `M600`.
- **Validates our SAVE → PARK → … → RESUME design**: capture state, park clear, restore.
- https://ellis3dp.com/Print-Tuning-Guide/articles/useful_macros/pause_resume_filament.html
- We deliberately **don't** use Klipper (would need reflashing the V3 SE).

### Marlin `M125` / `PARK_HEAD_ON_PAUSE` / `ADVANCED_PAUSE_FEATURE`  (official)

- Firmware-side "save nozzle position, move to park, return on resume." Needs
  `ADVANCED_PAUSE_FEATURE` + `PARK_HEAD_ON_PAUSE` compiled in.
- We do the **equivalent in the host** so nothing has to be enabled/flashed on a stock
  Creality board.
- https://marlinfw.org/docs/gcode/M125.html ·
  https://deepwiki.com/MarlinFirmware/Marlin/8.1-advanced-pause-and-filament-change

### Slicer "pause at layer"

- Cura *Pause at height*, PrusaSlicer *Insert pause (M601)*, Creality Print pause — all
  insert a pause **before a chosen layer**. The community rule: move the pause to the
  layer that **covers** the insert. This is what our `postprocess.py` automates, plus
  it carries the pocket coordinates.

---

## 3. Host G-code streaming — reference implementations

| Source | What we take from it |
|--------|----------------------|
| **Printrun `printcore.py`** (`github.com/kliment/Printrun`) | The `clear`-flag ack loop: send a line, wait for `ok`, then send the next. `_sender` / `_sendnext`. Resend handling. `pause()` saves the analyzer state; `resume()` restores it with G-code. |
| **OctoPrint `comm.py`** (`github.com/OctoPrint/OctoPrint`) | 10+ years of firmware-quirk handling: `wait` vs `busy: processing`, resend-without-ok, identical-resend suppression, long-running-command timeouts. Informed `links/_marlin_rx.py`. |
| **OctoPrint serial config schema** | The catalogue of every quirk toggle a real printer might need. |
| **OctoPrint virtual printer** (docs) | The model for our `SimPrinter` — a fake that speaks the protocol for offline testing. |
| **PyGcodeSender**, **gcode-cli** (`github.com/hzeller/gcode-cli`) | Minimal "line → wait ok → next" senders; confirm the simple approach is enough for a prototype. |
| **Moonraker** (Klipper's API server) | Considered and rejected (needs Klipper). Good REST model if we ever revisit. |

Key protocol facts that shaped the code:
- Marlin returns `ok` when a move is **buffered**, not finished → the insert sequence
  gates every phase with **`M400`**.
- Plain lines (no `N`-numbers / checksums) are fine for a prototype; add them only if the
  printer requests a `Resend:`.
- The Ender-3 V3 SE has documented OctoPrint/serial friction around `M110` — our
  plain-line streaming sidesteps it.

---

## 4. Pick-and-place hardware projects — for the feeder / mechanism (Phase 2)

Mostly built for **vacuum** pickup of SMD parts; our **magnetic pole** is simpler for
magnets, but the **feeder / escapement / rotation** ideas transfer.

| Project | Link | Relevant ideas |
|---------|------|----------------|
| **3DPlacer** — 3D-printer → P&P add-on | hackaday.io/project/191116 | part rotation, air pump, **nozzle change**, bottom vision, **feeder** designs; BOM on GitHub |
| **Micro_PNP** | `github.com/robotsmith/Micro_PNP` | P&P from 3D-printer parts + 2020 extrusion |
| **Picktor** | `github.com/celer/picktor` | 3D-printable P&P **head** on a printer, needle + vacuum pump |
| **LumenPnP** / Opulo | `github.com/opulo-inc/lumenpnp` | production open-source P&P; **drag/blow feeder** designs |
| **OpenPnP** | `github.com/openpnp/openpnp` | de-facto P&P control software; feeder abstractions, nozzle-tip changers, bottom vision |
| **Machdyne pnp** | `github.com/machdyne/pnp` | reference designs, vacuum + solenoid valve control |
| RepRap SMT Pick-n-Place | reprap.org/wiki/SMT_Pick-n-Place_System | early P&P-on-RepRap notes |

Feeder takeaway: an **escapement that isolates exactly one magnet** against
magnet-to-magnet attraction is the hard part — a single-pocket carousel or a
ratchet/gate driven by the one servo. Vibratory and drag feeders exist but are
overkill for a prototype magazine.

---

## 5. Community practice — embedding magnets via a pause  (feeds Phase 0)

From maker forums, Printables, vendor guides (Markforged, MLC-CAD, Prusa/Bambu forums):

- **Pocket oversize:** +0.1–0.3 mm over the magnet; e.g. a 10.2 mm hole for a 10.0 mm
  magnet — snug but seats without flying to the nozzle.
- **Cap layers:** leave **2–3 solid layers** above the insert before it's "sealed".
- **#1 warning:** *no part may protrude above its cavity* or it fouls the print-head
  path on the next pass. (Directly relevant to our "assume the applicator clears normal
  printing" assumption **and** to pocket depth vs. magnet thickness.)
- **Adhesion after pressing:** pushing an insert can smear **oil/grease** on the pocket
  walls → the next layer won't stick, worse if the insert and the last layer are cool.
  → keep the bed hot, consider a nozzle wipe, **use clean magnets**.
- **Resume-layer gaps:** ooze during the pause + imperfect prime → gaps on the first
  layer after resume. → our retract + `standby` temp + prime + wipe on RESUME.
- **Retention:** a dab of **CA glue** in the pocket stops the magnet pulling back out
  during the shear / in service. (Our press-fit + weak pole is the no-glue path; glue is
  the fallback.)
- **Layer shift:** more common with toolhead mods / PTFE guide tubes; keep the added
  applicator light and don't let the shear push the carriage.
- **Neodymium heat:** the cap-layer reheat is brief; N-grade working limit ≈ 80 °C, so
  a ~200 °C nozzle passing above is usually fine but repeated exposure can weaken it →
  move to N42SH/UH grade if strength drops.
- **Ferromagnetic nozzles and patterned bed plates** (Hackaday, 2026-06-04, added
  2026-09-18): many "brass" nozzles are magnetic enough for a loose magnet to jump to
  the nozzle, and a strong neodymium magnet near a modern alternating-pole magnetic
  bed plate can re-polarise the plate. → measure the magnet-to-nozzle pull at the real
  tool offset during the Phase 2 bench tests; keep the magazine and the pole clear of
  the plate; the "keep the pole holding the magnet until shear" rule stands.
- **Hand-held magnet placers exist** (EmGi "Magnet Insertion Tool" v1/v2, 2024 —
  magazine + magnetic tip + trigger release): a useful reference for the escapement and
  tip geometry of A2/A4, and prior art the disclosure now cites (Q5, Q19).

Sources: markforged.com/resources/blog/embedding-components-in-3d-printed-parts ·
mlc-cad.com/3d-printing-help-center/how-to-pause-printing-to-embed-hardware ·
forum.prusa3d.com (…/how-to-safely-insert-magnets-into-a-print) ·
forum.bambulab.com/t/gaps-in-layer-after-pausing-to-insert-drop-in-nut/70566 ·
forum.bambulab.com/t/don-t-embedded-magnet-s-interfere-with-the-print-head-s-movement/134038 ·
printables.com models 540969, 643002.

---

## 6. Ender-3 V3 SE specifics

- Marlin-based, USB-C serial **115200**, microSD, **no networking**, CR-Touch, dual-Z,
  Sprite direct-drive, ~250 mm/s.
- **Stock firmware ↔ OctoPrint friction** is documented; community forks exist purely for
  OctoPrint compatibility:
  - `github.com/navaismo/Ender-3V3-SE`
  - `github.com/ccarr0807/Ender-3V3-SE-update`
  - `github.com/pwlgrzs/awesome-resources-for-ender-3-v3-se` (OctoPrint section)
  - blog.octoeverywhere.com/ender3-v3-se-introduction-all-you-need-to-know/
- Mitigation for us: plain-line streaming (no `M110`), a liberal receive parser, and an
  early bench test of `SerialPrinter` against the real board.

---

## 7. Arduino serial

- Opening the port toggles **DTR** → the Uno resets (~2 s bootloader). Options: set
  `ser.dtr = False` **before** `open()`, or a 10 µF cap between RESET and GND, or wait it
  out. We do `dtr=False` + a `reset_settle_s` wait + PING-until-PONG in
  `SerialDispenser.connect()`.
- pyserial issue #124 (DTR/RTS toggle on open) ·
  forum.arduino.cc/t/serial-in-python-how-to-avoid-reset-on-opening/21552

---

## 8. What the research changed / confirmed in this project

| Finding | Effect on the project |
|---------|-----------------------|
| OctoPrint `@pause` = inert stream marker | Confirmed the **sentinel-as-comment** design; we went one further (a `;` comment, SD-safe, with parameters) |
| Klipper `PAUSE` saves z-hop + temp via `SET_GCODE_VARIABLE` | Confirmed **SAVE captures modes + temp + feed + position**, not just XY |
| Marlin `M125` is firmware-side | Confirmed doing **park/restore in the host** so the stock board needs nothing enabled |
| IEEE 2021 work uses a powered electromagnet + stepper + slip-ring + 2 cameras | Sharpened our **novelty framing**: no placement actuator, printer-motion press + **lateral shear**, no vision. Also a **risk flag** — closest prior art, must be in the patent search |
| OctoPNP: "let firmware handle tool offsets" | We can't (stock firmware) → **host-side offset transform + envelope check** is a conscious trade-off, documented |
| Community: pocket +0.1–0.3 mm, 2–3 cap layers, no protrusion, oil-on-walls | Straight into the **Phase 0 checklist** and `PROJECT_PLAN.md` §8 open questions |
| `ok` = buffered, not moved | Every insert phase gated with **`M400`** |
| Ender-3 V3 SE OctoPrint/`M110` friction | **Plain-line streaming**, liberal `_marlin_rx` parser, bench test early |
| Arduino DTR reset | `dtr=False` + settle + PING loop in `SerialDispenser` |
| Part-tray-on-bed staging (OctoPNP) | Recorded as an **alternative embodiment** (pick from a bed tray instead of a toolhead magazine) — see disclosure Q11 |

---

## 9. Link index

**Academic**
- Automated In-Situ Placing of Metal Components Into 3D Printed FFF Objects (IEEE 2021) — https://ieeexplore.ieee.org/document/9426422/ · https://www.researchgate.net/publication/351402100
- 3D-Printable Electronics — SMD Placement + Wiring into Slicing for FDM (2017) — https://www.researchgate.net/publication/319956919
- Embedding of SMD populated circuits into FDM printed objects (2017) — https://www.researchgate.net/publication/319956762
- Towards Integrating 3D Printing and Automated Assembly (2023) — https://www.researchgate.net/publication/374284221
- Printegrated Circuits (arXiv 2025) — https://arxiv.org/html/2509.08459v1

**Pick-and-place / integrated placement**
- OctoPNP — https://github.com/platsch/OctoPNP
- 3DPlacer — https://hackaday.io/project/191116-3dplacer-a-3d-printer-to-pick-and-place-add-on
- Micro_PNP — https://github.com/robotsmith/Micro_PNP
- Picktor — https://github.com/celer/picktor
- LumenPnP — https://github.com/opulo-inc/lumenpnp
- OpenPnP — https://github.com/openpnp/openpnp
- Machdyne pnp — https://github.com/machdyne/pnp

**Host control / firmware**
- OctoPrint @ commands — https://docs.octoprint.org/en/main/features/atcommands.html
- OctoPrint GCODE scripts — https://docs.octoprint.org/en/main/features/gcode_scripts.html
- OctoPrint-GCodeSystemCommands — https://github.com/kantlivelong/OctoPrint-GCodeSystemCommands
- OctoPrint comm.py — https://github.com/OctoPrint/OctoPrint/blob/main/src/octoprint/util/comm.py
- OctoPrint virtual printer — https://docs.octoprint.org/en/main/development/virtual_printer.html
- Printrun printcore.py — https://github.com/kliment/Printrun/blob/master/printrun/printcore.py
- gcode-cli — https://github.com/hzeller/gcode-cli
- Marlin G-code index — https://marlinfw.org/meta/gcode/
- Marlin M125 / Advanced Pause — https://marlinfw.org/docs/gcode/M125.html · https://deepwiki.com/MarlinFirmware/Marlin/8.1-advanced-pause-and-filament-change
- Marlin M400 — https://marlinfw.org/docs/gcode/M400.html
- Klipper pause/resume macros — https://ellis3dp.com/Print-Tuning-Guide/articles/useful_macros/pause_resume_filament.html

**Ender-3 V3 SE**
- navaismo/Ender-3V3-SE — https://github.com/navaismo/Ender-3V3-SE
- ccarr0807/Ender-3V3-SE-update — https://github.com/ccarr0807/Ender-3V3-SE-update
- awesome-resources-for-ender-3-v3-se — https://github.com/pwlgrzs/awesome-resources-for-ender-3-v3-se
- OctoEverywhere intro — https://blog.octoeverywhere.com/ender3-v3-se-introduction-all-you-need-to-know/

**Embedding practice**
- Markforged — https://markforged.com/resources/blog/embedding-components-in-3d-printed-parts
- MLC-CAD — https://www.mlc-cad.com/3d-printing-help-center/how-to-pause-printing-to-embed-hardware/
- Prusa forum — https://forum.prusa3d.com/forum/how-do-i-print-this-printing-help/how-to-safely-insert-magnets-into-a-print/
- Bambu forum: gaps after pausing for a nut — https://forum.bambulab.com/t/gaps-in-layer-after-pausing-to-insert-drop-in-nut/70566
- Bambu forum: do embedded magnets foul the head — https://forum.bambulab.com/t/don-t-embedded-magnet-s-interfere-with-the-print-head-s-movement/134038

**Arduino serial**
- pyserial DTR-on-open (#124) — https://github.com/pyserial/pyserial/issues/124
- Arduino forum: avoid reset on open — https://forum.arduino.cc/t/serial-in-python-how-to-avoid-reset-on-opening/21552
