"""Tkinter control panel.

Thin view over `magnet_embed.app.Controller`: buttons call the controller's
action methods; a 120 ms timer drains `controller.poll_events()` and updates the
widgets. All Tkinter work stays on the main thread.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk

from ..app import Controller
from ..state import PrinterState

_JOG_STEPS = (0.1, 1.0, 10.0)
_POLL_MS = 120


class ControlPanel(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: Controller) -> None:
        super().__init__(master, padding=10)
        self.c = controller
        self.step = tk.DoubleVar(value=1.0)
        self._prompt_open = False
        self._tick = 0
        poll_s = float(controller.config.get("ui", {}).get("idle_poll_s", 0) or 0)
        self._idle_poll_ticks = round(poll_s * 1000 / _POLL_MS) if poll_s > 0 else 0
        self._build()
        self.after(_POLL_MS, self._poll)

    # --- layout ----------------------------------------------------

    def _build(self) -> None:
        row = 0

        top = ttk.Frame(self)
        top.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(top, text="Connect", command=self.c.connect).pack(side="left")
        self.status = ttk.Label(top, text="not connected")
        self.status.pack(side="left", padx=8)
        row += 1

        files = ttk.Frame(self)
        files.grid(row=row, column=0, sticky="ew", pady=2)
        ttk.Button(files, text="Load G-code…", command=self._load).pack(side="left")
        self.btn_plan = ttk.Button(files, text="Plan magnet insert…", command=self._plan_insert)
        self.btn_plan.pack(side="left", padx=6)
        self.file_lbl = ttk.Label(files, text="(no file)")
        self.file_lbl.pack(side="left", padx=8)
        row += 1

        run = ttk.Frame(self)
        run.grid(row=row, column=0, sticky="ew", pady=4)
        self.btn_run = ttk.Button(run, text="Run", command=self.c.start_run)
        self.btn_pause = ttk.Button(run, text="Pause", command=self.c.pause)
        self.btn_resume = ttk.Button(run, text="Resume", command=self.c.resume)
        self.btn_cancel = ttk.Button(run, text="Cancel", command=self.c.cancel)
        for btn in (self.btn_run, self.btn_pause, self.btn_resume, self.btn_cancel):
            btn.pack(side="left", padx=2)
        row += 1

        prog = ttk.Frame(self)
        prog.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        self.progressbar = ttk.Progressbar(prog, mode="determinate")
        self.progressbar.pack(side="left", fill="x", expand=True)
        self.prog_lbl = ttk.Label(prog, text="—", width=20)
        self.prog_lbl.pack(side="left", padx=6)
        row += 1

        jog = ttk.LabelFrame(self, text="Jog / home  (idle only)", padding=6)
        jog.grid(row=row, column=0, sticky="ew", pady=4)
        for i, mm in enumerate(_JOG_STEPS):
            ttk.Radiobutton(jog, text=f"{mm} mm", value=mm, variable=self.step).grid(
                row=0, column=i, sticky="w"
            )
        buttons = (("X-", "X", -1), ("X+", "X", 1), ("Y-", "Y", -1),
                   ("Y+", "Y", 1), ("Z-", "Z", -1), ("Z+", "Z", 1))
        for i, (label, axis, sign) in enumerate(buttons):
            ttk.Button(
                jog, text=label, width=4,
                command=lambda a=axis, s=sign: self.c.jog(a, s * self.step.get()),
            ).grid(row=1 + i // 2, column=i % 2, padx=2, pady=1)
        ttk.Button(jog, text="Home", command=self.c.home).grid(row=1, column=2, padx=8)
        row += 1

        temp = ttk.LabelFrame(self, text="Temperature", padding=6)
        temp.grid(row=row, column=0, sticky="ew", pady=4)
        ttk.Label(temp, text="nozzle").grid(row=0, column=0)
        self.noz = ttk.Entry(temp, width=6)
        self.noz.insert(0, "0")
        self.noz.grid(row=0, column=1, padx=2)
        ttk.Button(temp, text="Set", width=4,
                   command=lambda: self.c.set_temp("nozzle", _to_int(self.noz))).grid(row=0, column=2)
        ttk.Label(temp, text="bed").grid(row=0, column=3, padx=(12, 0))
        self.bed = ttk.Entry(temp, width=6)
        self.bed.insert(0, "0")
        self.bed.grid(row=0, column=4, padx=2)
        ttk.Button(temp, text="Set", width=4,
                   command=lambda: self.c.set_temp("bed", _to_int(self.bed))).grid(row=0, column=5)
        row += 1

        fil = ttk.LabelFrame(self, text="Filament  (idle only)", padding=6)
        fil.grid(row=row, column=0, sticky="ew", pady=4)
        ttk.Label(fil, text="mm").grid(row=0, column=0)
        self.fil_mm = ttk.Entry(fil, width=6)
        self.fil_mm.insert(0, "5")
        self.fil_mm.grid(row=0, column=1, padx=2)
        ttk.Label(fil, text="feed").grid(row=0, column=2, padx=(12, 0))
        self.fil_feed = ttk.Entry(fil, width=6)
        self.fil_feed.insert(0, "300")
        self.fil_feed.grid(row=0, column=3, padx=2)
        self.btn_extrude = ttk.Button(fil, text="Extrude", command=lambda: self._filament(1))
        self.btn_extrude.grid(row=0, column=4, padx=(12, 2))
        self.btn_retract = ttk.Button(fil, text="Retract", command=lambda: self._filament(-1))
        self.btn_retract.grid(row=0, column=5, padx=2)
        row += 1

        cmd = ttk.LabelFrame(self, text="Send G-code  (idle only)", padding=6)
        cmd.grid(row=row, column=0, sticky="ew", pady=4)
        self.cmd_entry = ttk.Entry(cmd)
        self.cmd_entry.pack(side="left", fill="x", expand=True)
        self.cmd_entry.bind("<Return>", lambda _e: self._send_cmd())
        self.btn_send = ttk.Button(cmd, text="Send", command=self._send_cmd)
        self.btn_send.pack(side="left", padx=4)
        row += 1

        self.state_lbl = ttk.Label(self, text="position / temps: —")
        self.state_lbl.grid(row=row, column=0, sticky="w", pady=(4, 2))
        row += 1

        self.logbox = scrolledtext.ScrolledText(self, height=14, width=70, state="disabled")
        self.logbox.grid(row=row, column=0, sticky="nsew")
        self.rowconfigure(row, weight=1)
        self.columnconfigure(0, weight=1)

    # --- actions -------------------------------------------------

    def _filament(self, sign: int) -> None:
        self.c.extrude(sign * _to_float(self.fil_mm, 5.0), _to_float(self.fil_feed, 300.0))

    def _plan_insert(self) -> None:
        if self.c.gcode_path is None or self.c.running:
            return
        from .plan_dialog import PlanInsertDialog
        PlanInsertDialog(self.winfo_toplevel(), self.c)

    def _send_cmd(self) -> None:
        line = self.cmd_entry.get()
        if line.strip():
            self.c.send_command(line)
            self.cmd_entry.delete(0, "end")

    def _load(self) -> None:
        path = filedialog.askopenfilename(
            title="Load G-code",
            filetypes=[("G-code", "*.gcode *.gco *.g"), ("All files", "*.*")],
        )
        if path:
            self.c.load_gcode(path)
            self.file_lbl.configure(text=path.rsplit("/", 1)[-1])

    def log(self, message: str) -> None:
        self.logbox.configure(state="normal")
        self.logbox.insert("end", message + "\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    # --- event pump --------------------------------------------

    def _poll(self) -> None:
        self._tick += 1
        for kind, payload in self.c.poll_events():
            if kind == "log":
                self.log(str(payload))
            elif kind == "state":
                self._show_state(payload)  # type: ignore[arg-type]
            elif kind == "prompt":
                self._show_prompt(str(payload))
            elif kind == "done":
                self.log(f"run finished: {payload}")
                total = payload.get("total", 0) if isinstance(payload, dict) else 0
                if total:
                    self.progressbar.configure(maximum=total, value=total)
                    self.prog_lbl.configure(text=f"done {total}/{total}")
            elif kind == "error":
                self.log(f"ERROR: {payload}")

        if (
            self._idle_poll_ticks
            and self.c.connected
            and not self.c.running
            and self._tick % self._idle_poll_ticks == 0
        ):
            self.c.refresh_state()

        if self.c.running:
            done, total = self.c.progress
            if total:
                self.progressbar.configure(maximum=total, value=done)
                pct = done * 100 // total
                self.prog_lbl.configure(text=f"line {done} / {total} ({pct}%)")

        self._refresh_buttons()
        self.after(_POLL_MS, self._poll)

    def _show_state(self, st: PrinterState) -> None:
        self.status.configure(text="connected" if st.connected else "not connected")
        self.state_lbl.configure(
            text=(f"X{st.x:.1f} Y{st.y:.1f} Z{st.z:.2f}   "
                  f"nozzle {st.nozzle_temp:.0f}/{st.nozzle_target:.0f}   "
                  f"bed {st.bed_temp:.0f}/{st.bed_target:.0f}")
        )

    def _refresh_buttons(self) -> None:
        running = self.c.running
        self.btn_run.configure(
            state=("disabled" if running or self.c.gcode_path is None else "normal")
        )
        for btn in (self.btn_pause, self.btn_resume, self.btn_cancel):
            btn.configure(state=("normal" if running else "disabled"))
        idle_state = "disabled" if running else "normal"
        self.btn_send.configure(state=idle_state)
        self.cmd_entry.configure(state=idle_state)
        self.btn_extrude.configure(state=idle_state)
        self.btn_retract.configure(state=idle_state)
        self.btn_plan.configure(
            state=("disabled" if running or self.c.gcode_path is None else "normal")
        )

    def _show_prompt(self, stage: str) -> None:
        if self._prompt_open:
            return
        self._prompt_open = True
        if stage == "confirm":
            title = "Magnet inserted?"
            message = "Check the magnet seated correctly and the area is clear."
            options = (("Success", "success"), ("Retry", "retry"), ("Abort", "abort"))
        else:  # "dispense"
            title = "Load a magnet"
            message = "Place a magnet on the holding pole, then click Ready."
            options = (("Ready", "ready"), ("Abort", "abort"))

        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self.winfo_toplevel())
        dialog.resizable(False, False)
        ttk.Label(dialog, text=message, padding=16).pack()
        bar = ttk.Frame(dialog, padding=(8, 0, 8, 12))
        bar.pack()

        def choose(value: str) -> None:
            self._prompt_open = False
            dialog.grab_release()
            dialog.destroy()
            self.c.answer_prompt(value)

        for label, value in options:
            ttk.Button(bar, text=label, command=lambda v=value: choose(v)).pack(side="left", padx=4)
        dialog.protocol("WM_DELETE_WINDOW", lambda: None)  # a choice is required
        dialog.grab_set()


def _to_int(entry: ttk.Entry) -> int:
    try:
        return max(0, int(float(entry.get())))
    except (TypeError, ValueError):
        return 0


def _to_float(entry: ttk.Entry, default: float) -> float:
    try:
        return float(entry.get())
    except (TypeError, ValueError):
        return default


def run_gui(controller: Controller) -> None:
    root = tk.Tk()
    root.title("Magnet-Embedding Print Assistant")
    panel = ControlPanel(root, controller)
    panel.pack(fill="both", expand=True)
    root.mainloop()
