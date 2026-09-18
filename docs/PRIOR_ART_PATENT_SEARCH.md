# Prior-Art and Patent Search — Informal, 2026-09-18

| | |
|--|--|
| **Purpose** | Supplement Q5 / Q19 of `docs/INVENTION_DISCLOSURE_DRAFT.md` with patent references before the K&K agent runs the formal search. Complements `project/RESEARCH.md` (literature, open-source projects, maker practice — compiled 2026-09-09). |
| **Method** | General web search engine plus reading of the Google Patents record for each candidate (title, assignee, dates, abstract, independent claim 1, embodiments, status). No Espacenet / WIPO PATENTSCOPE / USPTO PatFT / Indian InPASS queries; no citation-tree walk; claims were read through automated page summaries, not the full specification. |
| **Status** | **Informal. Not a freedom-to-operate opinion and not a novelty opinion.** Everything here must be re-run and read in full by the agent (see §6). |
| **Confidential** | Part of the invention disclosure material. Do not publish. |

## Contents

1. [Headline findings](#1-headline-findings)
2. [Patent references, closest first](#2-patent-references-closest-first)
3. [Non-patent references new since `RESEARCH.md`](#3-non-patent-references-new-since-researchmd)
4. [Checked and excluded](#4-checked-and-excluded)
5. [What was *not* found](#5-what-was-not-found)
6. [Recommendations for the agent](#6-recommendations-for-the-agent)
7. [Effect on the disclosure draft](#7-effect-on-the-disclosure-draft)
8. [Sources](#8-sources)

---

## 1. Headline findings

1. **A Stratasys patent family from 2008 claims the general concept of an
   automated insert-placement apparatus on a layer-based printer** —
   US 8,070,473 B2 (system) and US 7,917,243 B2 (build-data method), with a
   granted European counterpart EP 2 231 375 B1. Independent claim 1 of the
   system patent is broad: a controller receiving build-sequence data, a head
   assembly forming layers, and *"an insert placement apparatus in signal
   communication with the controller, configured to place at least one insert
   in the plurality of formed layers based on the build sequence data."* The
   specification discloses a magazine-fed robotic arm with a vacuum effector,
   a **telescoping arm secured to the extrusion head**, and a **tape-dispensing
   unit on the head whose roller presses inserts from a tape into the part
   during deposition**. Google Patents shows the US patent active until
   **2029-06-26** and the EP until **2028-12-12**. This is the single most
   important reference for both novelty and freedom to operate. Whether the
   family was ever filed in India was **not** checked.
2. **A magazine-fed hand tool with a magnetic tip that places one magnet at a
   time already exists in the maker community** — EmGi's "Magnet Insertion
   Tool" v1 (2024) and v2 (self-reloading magazine, trigger release; 64 magnets
   placed without glue; one tool per polarity). The magazine + magnetic
   holding tip + polarity-by-tool idea is therefore not new *by itself*; what
   is not found anywhere is mounting such a feeder on the print carriage and
   using the **printer's own Z press and lateral shear** to seat and release.
3. **Pause-and-insert, manual, is extensively patented and published** as a
   step inside larger methods (Honeywell electronics housings 2024; orthotic
   sockets; composite robots; Markforged's removable kinematic platform;
   University of Texas structural electronics). None of these automates the
   placement on a stock single-tool printer.
4. **No reference was found** for: a G-code *comment* sentinel driving a
   host-side insert routine on an unmodified printer; a lateral shear release
   from a passive magnetic holder using the pocket wall as the reaction
   feature; or a collision guard for an offset tool derived from the
   toolpath's already-printed layers. Absence in an informal search is weak
   evidence — see §5.

## 2. Patent references, closest first

Relevance: **A** = must be cited and claim-charted; **B** = cite as background;
**C** = tangential.

| # | Reference | Assignee / dates | What it claims or discloses | Overlap with this invention | Difference | Rel. |
|---|-----------|------------------|-----------------------------|-----------------------------|------------|------|
| P1 | **US 8,070,473 B2** — *System for building three-dimensional objects containing embedded inserts, and method of use thereof* | Stratasys Inc; filed 2008-01-08, granted 2011-12-06, **expires 2029-06-26** (Google Patents); family EP 2 231 375 B1 (granted, expires 2028-12-12), PCT/US2008/013629, US 2009/0177309 A1 | Claim 1: controller + head assembly + **insert placement apparatus** placing inserts in formed layers per build-sequence data. Dependent claims: apparatus as a robotic arm, telescoping arm, or tape-dispensing unit; vacuum-based retrieval; z-axis platform. Embodiments: (a) chamber-mounted robotic arm picking from a **magazine** with a **vacuum effector**, build **pauses**; (b) **telescoping arm on the extrusion head** that retracts so deposition is not hindered; (c) **tape-dispensing unit on the head** with a compression roller pressing inserts from a tape into the part during deposition. Inserts pre-heated; pockets designed in CAD; "crown" inserts give a flat surface. CPC B29C70/70, B29C64/118, B29C64/307, B29C64/321, B33Y30/00, B33Y50/02. | Automated, controller-driven insert placement into pre-designed pockets during a layer-based build; a magazine; an apparatus **attached to the extrusion head** that must not hinder printing; the build pausing for the insert. | Every Stratasys embodiment has its own placement actuator (arm articulation, telescoping stroke, or a roller/tape drive) and holds the insert by vacuum or tape. Ours has **no placement actuator** — the only motion is a one-magnet feed; seating force and release come from the **printer's XYZ moves**; the insert is held **passively by magnetism** and released by a **lateral shear against the pocket wall**; the trigger is an **inert comment** in ordinary sliced G-code on an **unmodified consumer printer**, not build-sequence data from the OEM's own controller. | **A** |
| P2 | **US 7,917,243 B2** — *Method for building three-dimensional objects containing embedded inserts* | Stratasys Inc; filed 2008-01-08, granted 2011-03-29, expires 2029-08-10 (Google Patents); sibling of P1 | Claim 1: identify an insert's location in the CAD model, slice, generate support layers, generate an **unfilled region** at the insert location. Other claims: offset dimensions for clearance fits, and **pause times inserted into the build sequence** for placing the insert. Placement "manually or in an automated manner"; an automated apparatus is referenced but not detailed. | A pause marker generated into the build data at the insert layer; pocket clearance offsets. | The cavity is designed by the user in ordinary CAD, not generated from an "insert data representation"; our marker is a **comment added to an already-sliced file by a post-processor**, the slicer is untouched. | **A** |
| P3 | **US 8,858,856 B2 / US 9,566,743 B2 / US 10,226,916 B2** — *Method for building and using three-dimensional objects containing embedded identification-tag inserts* | Stratasys Inc (Kozlak, Chillscyzn, Batchelder); 9,566,743 granted 2017-02-14 | Placing an ID-tag insert on layers during the build (horizontal, vertical, near-vertical, bent-vertical placements; break-away tags). *Read from search summaries only, not the full record.* | Same family and same "place during build, encapsulate" concept as P1/P2. | Specific to ID tags; no placement mechanism of interest. | B |
| P4 | **US 9,539,762 B2** — *3D printing with kinematic coupling* | Markforged Inc; filed 2015-01-26, granted 2017-01-10 | Claim 1: printer with a build platform on a kinematic coupling (three protrusions, six locating features), flexures for Z, a **print-pause circuit**, removal/return detection, resume. Specification: pause at a preset completion, remove the platform, insert components (circuit boards), **glue via deposited pins/borders**, return and resume without re-levelling. | Pause → insert → seal workflow; adhesive retention as an option. | Manual insertion off the machine; the invention is the repeatable platform coupling, not the placement. | B |
| P5 | **US 11,981,094 B2** — *Embedding electronics in housing using additive manufacturing* | Honeywell International Inc; filed 2020-09-30, granted 2024-05-14 | Claim 1: fabricate supports for an angled housing, additively manufacture the housing, **pause before completion, insert the electronics assembly, resume**. | Pause-insert-resume as a claimed method step (recent grant). | Manual insertion; no marker, no placement tool. Shows the pause-insert-resume step is patentable as part of a larger method but is itself well known. | B |
| P6 | **US 10,748,867 B2** — *Extrusion-based additive manufacturing system for 3D structural electronic, electromagnetic and electromechanical components/devices* | University of Texas System; filed 2012-01-04, granted 2020-08-18 | Claim 1: FDM substrate build, **pausing intermittently**, micro-machining cavities, filling interconnect cavities with conductor, **placing electrical components into component cavities**. | Intermittent pauses of an FDM build to place components in cavities. | Cavities machined after the fact; placement by hand or separate pick-and-place equipment; no printer-motion press. | B |
| P7 | **US 10,582,619 B2** (pub. US 2017/0064840 A1) — *Method and apparatus for wire handling and embedding on and within 3D printed parts* | University of Texas System; filed 2016-08-23, granted 2020-03-03 | Claim 1: a **direct wire embedding head fixed on an automation motion system** that starts and ends an embedded wire pattern on a layer; heated exit tip; distance sensor. | An embedding tool carried by the printer's motion system. | Wire only, embedded by heat; not discrete inserts; not a feeder. | B |
| P8 | **US 9,076,097 B1** — *Pausing and resuming a three-dimensional printjob* | IBM; filed 2013-12-18, granted 2015-07-07 | Claim 1: begin a print job, pause with the object incomplete, determine the job state, **print the state as a barcode onto the incomplete object** so the job can resume later, possibly on another printer. Host-side control logic. | Host-side pause/resume with saved state. | State goes onto the part as a barcode; nothing about inserts. | C |
| P9 | **US 10,363,706 B2** — *Three dimensional printing method and apparatus using the same* | Kinpo Electronics / XYZprinting; filed 2016-03-09, granted 2019-07-30 | Prints the whole object with separation planes of support material so an embedded object can be placed **after** printing, explicitly to avoid the platform/head **shift caused by pausing to place an object**. | Documents the pause-and-insert misalignment problem our SAVE/RESUME and no-homing rules address. | Opposite approach (no pause). | C |
| P10 | **US 10,406,758 B2** — *System and method for 3D printing parts with additional features* | Robotic Research Opco LLC; filed 2014-11-12, granted 2019-09-10 | Additional nozzles emitting chemicals for insulation, sterilisation and embedding of fibre/paper onto or into a part still in the chamber. | "Embedding" in the title only. | No discrete-insert placement mechanism. | C |
| P11 | **US 9,469,072 B2** — *Three-dimensional printer tool systems* | MakerBot / Stratasys; filed 2014-12-23, granted 2016-10-18 | Tool crib, robotic tool exchange, spring-biased extruder; magnets used for tool coupling. | Tool changing on a desktop printer. | Nothing on inserts. | C |
| P12 | Pause-and-insert as a step in other patents (titles from USPTO full-text search, **not read**): US 12,150,870 / US 11,058,557 (orthotic-prosthetic sockets — technician installs a connection insert at a pause, printing resumes over it); US 12,128,721 (composite robots — bed removed mid-print, bearings and splines inserted and glued); US 9,656,428 (embedded ID elements). | various | Manual pause-insert-resume inside larger methods. | Confirms how common the manual step is. | None automate it. | C |

## 3. Non-patent references new since `RESEARCH.md`

| # | Reference | What it is | Why it matters here |
|---|-----------|------------|---------------------|
| N1 | **EmGi — "Magnet Insertion Tool" v1** (Printables model 975729; Hackaday "An Attractive Magnet Insertion Tool", 2024-09-01) and **v2** (Printables 1008467 / MakerWorld 647269; Patreon post; YouTube "Designing a magnet insertion tool with automated reloading") | Hand-held, 3D-printed, finger-operated tool: a **self-reloading magazine** feeds one magnet at a time to a tip that holds it **by an embedded magnet**; a trigger releases it into the pocket. Supports 5×1 to 8×3 mm magnets; 64 magnets placed with no glue; **two tools, one per polarity**. (v2 page returned HTTP 403 — details from the Hackaday article and search summaries.) | Closest non-patent art to components A2 + A4 and to novelty item 4 (deterministic polarity from a magnetic holder + uniformly loaded magazine). Establishes that the **feeder-plus-magnetic-tip idea is public since 2024**. Not printer-mounted; release is by a hand trigger, not by printer motion; no integration with the print. |
| N2 | **"Embedded Magnet Dispenser Tool for 3D Prints"** (MakerWorld model 60890) | Another hand dispenser "to ensure correct orientation and secure fitting" (page returned HTTP 403 — not read). | Same category as N1; agent to read. |
| N3 | **Hackaday, "Ways To Embed Magnets In 3D Prints And Not Ruin Printers"**, Maya Posch, 2026-06-04 | Survey of post-print vs mid-print magnet embedding. Warnings: many "brass" nozzles are **ferromagnetic enough for a magnet to jump to the nozzle**; modern **magnetic bed plates with alternating pole patterns can be re-polarised** by a strong neodymium magnet nearby; magnets demagnetise well below 200 °C; recommends side-insertion so the nozzle cannot pull the magnet out. | Two new engineering risks for `project/PROJECT_PLAN.md` §7: magnet-to-nozzle attraction during APPROACH/PRESS (our pole is 30 mm from the nozzle by default — measure), and bed-plate pattern damage (already listed as "magnet snaps to the steel flex plate"; the re-polarisation angle is new). Also confirms the market problem statement in Q2. |
| N4 | **"Development of Integrated 3D Printing and Automated Embedding System"**, 21st Mechatronika 2024, Brno, IEEE, pp. 367–372, DOI 10.1109/ME61309.2024.10789740 (Czech project GC22-14387J) | Automated embedding for **bottom-up vat photopolymerisation**: the object is fixed at the bottom of the resin tank directly beneath the model's cavity before sealing, so printing continues uninterrupted; prototype couples a resin printer with **SMT placement equipment**; no printer hardware modification. | Recent (Dec 2024) academic "automated embedding without modifying the printer" claim — for resin, not FFF; placement by external SMT equipment. Cite alongside the IEEE 2021 / OctoPNP work in Q5. |
| N5 | **Yuen, P. K., "Embedding objects during 3D printing to add new functionalities", *Biomicrofluidics* 10, 044104 (2016)** | FDM embedding of cover slips, films, membranes and optical fibre; **drops of glue fix the object so the nozzle cannot move it**. | Peer-reviewed statement of the pause-insert-seal method and of glue-assisted retention (our Q11 retention variant). |
| N6 | **Hackaday, "See the pause-and-attach technique for 3D printing in action"**, 2024-10-05 (3DPrintBunny) | Pause, manually attach separately printed pieces into sockets, resume. | Manual; shows the general "pause and add" idea is widely practised. |
| N7 | Slicer / vendor pause features: Bambu Studio "add a pause … for magnets, hardware inserts" (FettesPS guide); Prusa forum "print a tall sacrificial object far from the insert so the nozzle is elsewhere while you place it" | Current manual practice on the two most common consumer platforms. | Background for Q4. Bambu Lab's published patents (automatic print-head exchange, nozzle camera) do not cover insert placement. |
| N8 | **OctoPNP / Plätzsch et al.** — searched for a patent filing (DE/EP/US) | **No patent application found** for the OctoPNP line of work; only the 2021 IEEE paper, the GitHub plugin and a University of Hamburg seminar report. | The closest academic art appears to be unpatented (to be confirmed by the agent). |

## 4. Checked and excluded

Read and found not relevant: US 10,838,404 B2 (Advanced Solutions Life Sciences —
robotic design/assembly workstation, no inserts); US 10,150,258 B2 / US
2016/0167312 A1 (Carnegie Mellon — printing into a viscoplastic support bath);
US 9,346,219 B2 (MakieWorld/Disney — parametric model customisation, "internal
components" are mesh parts, not physical inserts); US 2025/0018598 A1 (robotic
concrete printer collision avoidance); permanent-magnet *manufacturing* patents
(US 12,308,163, US 11,862,369, US 10,840,754, US 2017/0092400 — printing the
magnet itself, not inserting one); CN 210100713U (magnetic-levitation printer).

## 5. What was *not* found

No hit, in this informal search, for any of the following. The agent should
search for them specifically before relying on their absence:

- A **G-code comment** (or other inert marker) in an ordinary sliced file that a
  host detects to run an insert routine on an **unmodified** printer, with the
  file still valid for standalone printing. (OctoPrint's `@` commands are the
  nearest mechanism — `project/RESEARCH.md` §2 — and carry no placement data.)
- Seating an insert with the **printer's own Z move** and releasing it with a
  **lateral move against the pocket wall** from a **passive magnetic holder**.
  The nearest concept is P1's tape-dispensing roller pressing inserts during
  deposition — the agent must read that embodiment and its claims in full.
- A **collision guard for an offset secondary tool** computed from the
  **already-printed portion of the toolpath** at the time of the insert.
  Multi-axis toolpath collision-avoidance patents exist for the *printing*
  tool (e.g. US 2021/0055710 A1 continuous toolpaths; multi-axis planning
  papers) but not for an offset placement tool at a pause.
- Any **Indian** patent or application on automated in-situ insertion. Indian
  filings were not queried at all (InPASS is not reachable through a general
  search engine).
- Any patent assigned to the OctoPNP authors.

## 6. Recommendations for the agent

1. **Claim-chart P1 (US 8,070,473 B2 / EP 2 231 375 B1) against our system**,
   claim by claim, and check whether Stratasys has an **Indian** family member
   or any pending continuation. Its claim 1 reads on any controller-driven
   "insert placement apparatus" — the question is whether an applicator with
   no placement actuator, where the printer's motion does the placing, falls
   inside it. This drives both the novelty framing (Q9 items 1–2) and freedom
   to operate in the US until 2029-06-26 and in the EP states until 2028-12-12.
2. Walk the **"cited by"** list of P1 and P2 on Espacenet / Google Patents
   (the Google page fetched here did not render that section).
3. Run classification searches in **B29C 70/70** (completely encapsulating
   inserts), **B29C 64/118**, **B29C 64/307** and **64/321** (material
   handling / feeding), **B33Y 30/00**, **B33Y 50/02**, and **B29C 64/386–393**
   (data processing / process planning), combined with keywords *insert,
   magnet, embed, pause, place*.
4. Search **InPASS** (Indian Patent Advanced Search) with the Q3 search terms
   and the CPC classes above.
5. Read P3, P12, N1 (v2 page), N2 and N4 in full — this draft only has search
   summaries for them.
6. Treat **novelty item 4** of the disclosure (deterministic polarity from a
   magnetic holder + uniformly loaded magazine) as a **dependent** feature
   only, given N1. Keep the independent claims on items 1–3 and 7.
7. Search specifically for the three "not found" mechanisms in §5 before the
   agent's novelty opinion rests on them.

## 7. Effect on the disclosure draft

Applied on 2026-09-18 in `docs/INVENTION_DISCLOSURE_DRAFT.md`:

- Q5 gained a "Patent references (informal search)" block pointing here, with
  P1, P2, P4, P5, P6, N1 and N4.
- Q6 and Q9 note that the general "insert placement apparatus" concept is
  already claimed by P1 and that item 4 is weakened by N1.
- Q19 gained rows for P1/P2 and N1 and now records which databases were used.
- Q27 lists the two new engineering risks from N3.

Nothing here changes the mechanism or the software.

## 8. Sources

**Patents (Google Patents records read)**
- US 8,070,473 B2 — https://patents.google.com/patent/US8070473B2/en
- EP 2 231 375 B1 — https://patents.google.com/patent/EP2231375B1/en
- US 7,917,243 B2 — https://patents.google.com/patent/US7917243B2/en
- US 9,539,762 B2 — https://patents.google.com/patent/US9539762B2/en
- US 11,981,094 B2 — https://patents.google.com/patent/US11981094B2/en
- US 10,748,867 B2 — https://patents.google.com/patent/US10748867B2/en
- US 2017/0064840 A1 (→ US 10,582,619 B2) — https://patents.google.com/patent/US20170064840A1/en
- US 9,076,097 B1 — https://patents.google.com/patent/US9076097
- US 10,363,706 B2 — https://patents.google.com/patent/US10363706B2/en
- US 10,406,758 B2 — https://patents.google.com/patent/US10406758B2/en
- US 9,469,072 B2 — https://patents.google.com/patent/US9469072B2/en
- US 10,838,404 B2 — https://patents.google.com/patent/US10838404B2/en
- US 2016/0167312 A1 — https://patents.google.com/patent/US20160167312A1/en
- US 9,346,219 B2 — https://patents.google.com/patent/US9346219B2/en

**Patents (titles from search results only, not read)**
- US 8,858,856 — https://patents.google.com/patent/US8858856 · US 9,566,743 — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9566743 · US 10,226,916 — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10226916
- US 12,150,870 — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12150870 · US 11,058,557 — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11058557
- US 12,128,721 — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12128721
- US 9,656,428 — https://patents.google.com/patent/US9656428
- US 2021/0055710 A1 — https://patents.google.com/patent/US20210055710A1/en
- US 2025/0018598 A1 — https://patents.google.com/patent/US20250018598A1/en

**Non-patent**
- Hackaday, "An Attractive Magnet Insertion Tool" (2024-09-01) — https://hackaday.com/2024/09/01/an-attractive-magnet-insertion-tool/
- EmGi, Magnet Insertion Tool v1 — https://www.printables.com/model/975729-magnet-insertion-tool-v1
- EmGi, Magnet Insertion Tool v2 — https://www.printables.com/model/1008467-magnet-insertion-tool-v2 · https://makerworld.com/en/models/647269-magnet-insertion-tool-v2 · https://www.patreon.com/posts/version-2-of-if-112223722 · https://www.youtube.com/watch?v=k0yt9EvjzNI
- Embedded Magnet Dispenser Tool (MakerWorld 60890) — https://makerworld.com/en/models/60890-embedded-magnet-dispenser-tool-for-3d-prints
- Hackaday, "Ways To Embed Magnets In 3D Prints And Not Ruin Printers" (2026-06-04) — https://hackaday.com/2026/06/04/ways-to-embed-magnets-in-3d-prints-and-not-ruin-printers/
- Hackaday, "See The 'Pause-and-Attach' Technique…" (2024-10-05) — https://hackaday.com/2024/10/05/see-the-pause-and-attach-technique-for-3d-printing-in-action/
- Mechatronika 2024, "Development of Integrated 3D Printing and Automated Embedding System" — https://ieeexplore.ieee.org/document/10789740/ · https://starfos.tacr.cz/en/vysledky-vyzkumu/RIV%2F00216305:26210%2F24:PU155222
- Yuen 2016, Biomicrofluidics — https://pubmed.ncbi.nlm.nih.gov/27478528/ · https://pmc.ncbi.nlm.nih.gov/articles/PMC4947038/
- Bambu Studio pause guide — https://www.fettesps.com/how-to-add-a-pause-when-printing-in-bambu-studio/
- Prusa forum, pausing to insert items — https://forum.prusa3d.com/forum/original-prusa-i3-mk3s-mk3-print-tips-archive/pausing-print-job-to-insert-non-3d-printed-items/
- Bambu Lab patents (3D Printing Industry) — https://3dprintingindustry.com/news/bambu-lab-patents-detail-automatic-printhead-changing-and-nozzle-monitoring-systems-254247/
- OctoPNP — https://github.com/platsch/OctoPNP · University of Hamburg seminar report — https://tams.informatik.uni-hamburg.de/lectures/2019ss/seminar/oberseminar/doc/kolwa_pnp_3d-printer.pdf
- Stratasys Direct, "An easy way to add inserts into FDM parts" — https://www.stratasys.com/en/stratasysdirect/resources/articles/fdm-adding-inserts/
- EZN, "Additive manufacturing of components with inserts" (patent-offer listing) — https://www.ezn.de/en/ezn-patent/additive-manufacturing-3d-printing-of-components-with-inserts/
- ASME IDETC 2019, "Digital Design Automation to Support In-Situ Embedding of Functional Components in Additive Manufacturing" — https://asmedigitalcollection.asme.org/IDETC-CIE/proceedings-abstract/IDETC-CIE2019/59186/V02AT03A031/1069733
