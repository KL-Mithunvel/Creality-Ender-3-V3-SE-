"""'Z Calibrate…' dialog - a guided paper-test Z-offset calibration (C21).

Homes, moves the nozzle to `config.zcal.{x,y,start_z}`, then lets the operator
nudge it down in small steps over a sheet of paper until it just grips. "Save"
applies the accumulated nudge to `config.zcal.probe_z_offset`, pushes the
result to the firmware (`M851` + `M500`), and persists it to
`config.local.yaml` (`Controller.save_z_offset`).

DEV NOTE - unlike most of this app, a mistake here can physically drive the
nozzle into the bed: this workflow has only been exercised against
`SimPrinter`, never bench-tested on the real V3 SE. Steps default small,
every homing/nudge/save action needs an explicit confirm, and the offset
math never trusts a value read back from the printer (see
`Controller.save_z_offset`'s docstring and `.CLAUDE/CLAUDE.md` -> Known
Technical Debt). Treat the first real run as commissioning, not routine use.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

_STEPS = (0.5, 0.1, 0.05, 0.02, 0.01)


class ZCalDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, controller) -> None:
        super().__init__(master)
        self.title("Z-offset calibration")
        self.resizable(False, False)
        self.c = controller
        self.started = False
        self.cumulative = 0.0
        self.step = tk.DoubleVar(value=_STEPS[2])

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="Paper-test Z-offset calibration. Homes, then moves the nozzle\n"
                 "above the configured bed point. Slide a sheet of paper under\n"
                 "the nozzle and nudge it down until you feel slight drag, then\n"
                 "Save. Watch the printer the whole time.",
            wraplength=360, foreground="#c23a3a", justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.btn_start = ttk.Button(
            frm, text="Home + move to calibration point", command=self._start
        )
        self.btn_start.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(frm, text="step (mm)").grid(row=2, column=0, sticky="w")
        ttk.Combobox(
            frm, textvariable=self.step, values=_STEPS, width=6, state="readonly",
        ).grid(row=2, column=1, sticky="w")

        nudge = ttk.Frame(frm)
        nudge.grid(row=3, column=0, columnspan=3, sticky="w", pady=6)
        self.btn_down = ttk.Button(nudge, text="Nozzle down ▼", command=lambda: self._nudge(-1))
        self.btn_down.pack(side="left", padx=2)
        self.btn_up = ttk.Button(nudge, text="Nozzle up ▲", command=lambda: self._nudge(1))
        self.btn_up.pack(side="left", padx=2)

        self.status = ttk.Label(frm, text="not started", wraplength=360, justify="left")
        self.status.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 8))

        bar = ttk.Frame(frm)
        bar.grid(row=5, column=0, columnspan=3, sticky="e")
        self.btn_save = ttk.Button(bar, text="Save Z-offset", command=self._save)
        self.btn_save.pack(side="left", padx=4)
        ttk.Button(bar, text="Close", command=self._close).pack(side="left", padx=4)

        self._set_nudge_state("disabled")
        self._refresh_status()

    def _set_nudge_state(self, state: str) -> None:
        self.btn_down.configure(state=state)
        self.btn_up.configure(state=state)
        self.btn_save.configure(state=state)

    def _start(self) -> None:
        if not messagebox.askyesno(
            "Home and move?",
            "This homes all axes, then moves the nozzle to the configured\n"
            "calibration point close to the bed. Make sure the bed is clear\n"
            "and you can reach the power switch. Continue?",
            parent=self,
        ):
            return
        self.c.start_z_calibration()
        self.started = True
        self.cumulative = 0.0
        self._set_nudge_state("normal")
        self.btn_start.configure(state="disabled")
        self._refresh_status()

    def _nudge(self, sign: int) -> None:
        delta = sign * float(self.step.get())
        self.c.nudge_z(delta)
        self.cumulative += delta
        self._refresh_status()

    def _refresh_status(self) -> None:
        current = self.c.config["zcal"]["probe_z_offset"]
        preview = current + self.cumulative
        if not self.started:
            self.status.configure(
                text=f"not started - current saved offset {current:.3f} mm"
            )
        else:
            self.status.configure(
                text=f"nudged {self.cumulative:+.3f} mm so far   "
                     f"(saved offset {current:.3f} -> would save {preview:.3f} mm)"
            )

    def _save(self) -> None:
        if not self.started or abs(self.cumulative) < 1e-9:
            messagebox.showinfo("Nothing to save", "Home + nudge the nozzle first.", parent=self)
            return
        if not messagebox.askyesno(
            "Save new Z-offset?",
            "This writes a new probe Z-offset to the printer (M851 + M500) and\n"
            "to config.local.yaml. It changes how close the nozzle gets to the\n"
            "bed on every future print. Only confirm once you have visually\n"
            "verified the nozzle position against the paper. Continue?",
            parent=self,
        ):
            return
        self.c.save_z_offset(self.cumulative)
        self.cumulative = 0.0
        messagebox.showinfo("Saved", "Z-offset saved.", parent=self)
        self._close()

    def _close(self) -> None:
        if self.started:
            # never leave the nozzle sitting near the plate, saved or not
            self.c.jog("Z", self.c.config["park"]["safe_z_lift_mm"])
        self.destroy()
