"""Tkinter control panel.

Thin view over `magnet_embed.app.Controller`: buttons call the controller's
action methods; a 120 ms timer drains `controller.poll_events()` and updates the
widgets. All Tkinter work stays on the main thread.

The whole panel is wrapped in a scrollable canvas (`_build_scroll_container`)
so nothing gets clipped off-screen on a shorter display - everything below
used to be built directly on `self`; it now lives in `self.body` instead.

Embeds a small live-print view (current layer + nozzle marker + current-step
G-code text, `_sync_live_view`) driven off `Controller.toolpath` /
`progress_point` - derived from G-code line progress against the parsed
toolpath, so it costs no extra printer traffic and never contends with the
streaming loop's own serial handshake. A "3D" toggle swaps it for an isometric
view of the whole part (`viz.toolpath_fig.draw_live_3d`).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers the 3d projection)

from ..app import Controller
from ..state import PrinterState
from ..viz import toolpath_fig as tf

_JOG_STEPS = (0.1, 1.0, 10.0)
_POLL_MS = 120


class ControlPanel(ttk.Frame):
    def __init__(self, master: tk.Misc, controller: Controller) -> None:
        super().__init__(master)
        self.c = controller
        self.step = tk.DoubleVar(value=1.0)
        self._prompt_open = False
        self._tick = 0
        poll_s = float(controller.config.get("ui", {}).get("idle_poll_s", 0) or 0)
        self._idle_poll_ticks = round(poll_s * 1000 / _POLL_MS) if poll_s > 0 else 0
        live_poll_s = float(controller.config.get("ui", {}).get("live_view_poll_s", 0) or 0)
        self._live_view_ticks = round(live_poll_s * 1000 / _POLL_MS) if live_poll_s > 0 else 0
        self._live_tp = None
        self._live_layer = -1
        self._live_art: dict = {}
        self.live_3d = False
        self._build_scroll_container()
        self._build()
        self.after(_POLL_MS, self._poll)

    # --- scrolling shell --------------------------------------------

    def _build_scroll_container(self) -> None:
        """Wrap the whole panel in a Canvas + Scrollbar so tall content (jog,
        temps, filament, send G-code, log...) never gets clipped by a screen
        shorter than the panel's natural height - it scrolls instead."""
        canvas = tk.Canvas(self, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.body = ttk.Frame(canvas, padding=10)
        window = canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))

        def _wheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # bind/unbind the wheel only while the pointer is over this canvas, so
        # scrolling elsewhere (e.g. a Combobox in a dialog) isn't hijacked.
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    # --- layout ----------------------------------------------------

    def _build(self) -> None:
        b = self.body
        row = 0

        top = ttk.Frame(b)
        top.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(top, text="Connect", command=self.c.connect).pack(side="left")
        self.status = ttk.Label(top, text="not connected")
        self.status.pack(side="left", padx=8)
        self.target_lbl = ttk.Label(top, text=f"({self.c.link_summary})", foreground="gray")
        self.target_lbl.pack(side="left")
        ttk.Button(top, text="Settings…", command=self._open_settings).pack(side="left", padx=(12, 0))
        row += 1

        files = ttk.Frame(b)
        files.grid(row=row, column=0, sticky="ew", pady=2)
        ttk.Button(files, text="Load G-code…", command=self._load).pack(side="left")
        self.btn_plan = ttk.Button(files, text="Plan magnet insert…", command=self._plan_insert)
        self.btn_plan.pack(side="left", padx=6)
        self.file_lbl = ttk.Label(files, text="(no file)")
        self.file_lbl.pack(side="left", padx=8)
        row += 1

        run = ttk.Frame(b)
        run.grid(row=row, column=0, sticky="ew", pady=4)
        self.btn_run = ttk.Button(run, text="Run", command=self.c.start_run)
        self.btn_pause = ttk.Button(run, text="Pause", command=self.c.pause)
        self.btn_resume = ttk.Button(run, text="Resume", command=self.c.resume)
        self.btn_cancel = ttk.Button(run, text="Cancel", command=self.c.cancel)
        for btn in (self.btn_run, self.btn_pause, self.btn_resume, self.btn_cancel):
            btn.pack(side="left", padx=2)
        row += 1

        prog = ttk.Frame(b)
        prog.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        self.progressbar = ttk.Progressbar(prog, mode="determinate")
        self.progressbar.pack(side="left", fill="x", expand=True)
        self.prog_lbl = ttk.Label(prog, text="—", width=20)
        self.prog_lbl.pack(side="left", padx=6)
        row += 1

        live = ttk.LabelFrame(b, text="Live print view", padding=4)
        live.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        live_hdr = ttk.Frame(live)
        live_hdr.pack(fill="x")
        ttk.Label(live_hdr, text="current layer, nozzle position").pack(side="left")
        self.btn_live_dim = ttk.Button(live_hdr, text="3D view", width=8, command=self._toggle_live_dim)
        self.btn_live_dim.pack(side="right")
        self.live_fig = Figure(figsize=(4.6, 3.0), dpi=90)
        self.live_ax = self.live_fig.add_subplot(1, 1, 1)
        self.live_canvas = FigureCanvasTkAgg(self.live_fig, master=live)
        self.live_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.live_line_lbl = ttk.Label(live, text="current step: —", anchor="w")
        self.live_line_lbl.pack(fill="x", pady=(4, 0))
        row += 1

        jog = ttk.LabelFrame(b, text="Jog / home  (idle only)", padding=6)
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

        # Two distinct calibrations, captioned so it's clear why both exist:
        # Level Bed probes/saves the ABL mesh (overall bed tilt); Z Calibrate
        # tunes the single nozzle-to-bed offset (first-layer height).
        calib = ttk.Frame(jog)
        calib.grid(row=1, column=3, rowspan=2, sticky="nw", padx=(16, 0))
        self.btn_level = ttk.Button(calib, text="Level Bed…", width=14, command=self._level_bed)
        self.btn_level.grid(row=0, column=0, sticky="w")
        ttk.Label(calib, text="probe + save bed mesh", foreground="gray").grid(
            row=1, column=0, sticky="w"
        )
        self.btn_zcal = ttk.Button(calib, text="Z Calibrate…", width=14, command=self._zcal)
        self.btn_zcal.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(calib, text="paper-test nozzle offset", foreground="gray").grid(
            row=3, column=0, sticky="w"
        )
        row += 1

        temp = ttk.LabelFrame(b, text="Temperature  (works during a print too)", padding=6)
        temp.grid(row=row, column=0, sticky="ew", pady=4)
        temps_cfg = self.c.config.get("temps", {})
        noz_lo = temps_cfg.get("nozzle_min_c", 0)
        noz_hi = temps_cfg.get("nozzle_max_c", 260)
        bed_lo = temps_cfg.get("bed_min_c", 0)
        bed_hi = temps_cfg.get("bed_max_c", 100)

        ttk.Label(temp, text="nozzle").grid(row=0, column=0)
        self.noz = ttk.Entry(temp, width=6)
        self.noz.insert(0, "0")
        self.noz.grid(row=0, column=1, padx=2)
        ttk.Button(temp, text="Set", width=4,
                   command=lambda: self.c.set_temp("nozzle", _to_int(self.noz))).grid(row=0, column=2)
        self.noz_now = ttk.Label(temp, text="now: —", width=16)
        self.noz_now.grid(row=0, column=3, padx=(10, 0))
        ttk.Label(temp, text=f"allowed {noz_lo:g}–{noz_hi:g}°C",
                  foreground="gray").grid(row=1, column=0, columnspan=4, sticky="w")

        ttk.Label(temp, text="bed").grid(row=2, column=0, pady=(8, 0))
        self.bed = ttk.Entry(temp, width=6)
        self.bed.insert(0, "0")
        self.bed.grid(row=2, column=1, padx=2, pady=(8, 0))
        ttk.Button(temp, text="Set", width=4,
                   command=lambda: self.c.set_temp("bed", _to_int(self.bed))).grid(row=2, column=2, pady=(8, 0))
        self.bed_now = ttk.Label(temp, text="now: —", width=16)
        self.bed_now.grid(row=2, column=3, padx=(10, 0), pady=(8, 0))
        ttk.Label(temp, text=f"allowed {bed_lo:g}–{bed_hi:g}°C",
                  foreground="gray").grid(row=3, column=0, columnspan=4, sticky="w")
        row += 1

        fil = ttk.LabelFrame(b, text="Filament  (idle only)", padding=6)
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

        cmd = ttk.LabelFrame(b, text="Send G-code  (idle only)", padding=6)
        cmd.grid(row=row, column=0, sticky="ew", pady=4)
        self.cmd_entry = ttk.Entry(cmd)
        self.cmd_entry.pack(side="left", fill="x", expand=True)
        self.cmd_entry.bind("<Return>", lambda _e: self._send_cmd())
        self.btn_send = ttk.Button(cmd, text="Send", command=self._send_cmd)
        self.btn_send.pack(side="left", padx=4)
        row += 1

        self.state_lbl = ttk.Label(b, text="position / temps: —")
        self.state_lbl.grid(row=row, column=0, sticky="w", pady=(4, 2))
        row += 1

        self.logbox = scrolledtext.ScrolledText(b, height=14, width=70, state="disabled")
        self.logbox.grid(row=row, column=0, sticky="nsew")
        b.rowconfigure(row, weight=1)
        b.columnconfigure(0, weight=1)

    # --- actions -------------------------------------------------

    def _filament(self, sign: int) -> None:
        self.c.extrude(sign * _to_float(self.fil_mm, 5.0), _to_float(self.fil_feed, 300.0))

    def _level_bed(self) -> None:
        if messagebox.askyesno(
            "Level bed?",
            "Homes all axes, then probes a fresh bed mesh, enables it, and "
            "saves it to EEPROM. Moves the toolhead over the whole bed and "
            "can take a couple of minutes - the panel will be unresponsive "
            "until it finishes. Continue?",
            parent=self,
        ):
            self.c.level_bed()

    def _open_settings(self) -> None:
        from .settings_dialog import SettingsDialog
        SettingsDialog(self.winfo_toplevel(), self.c)

    def _zcal(self) -> None:
        from .zcal_dialog import ZCalDialog
        ZCalDialog(self.winfo_toplevel(), self.c)

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

    def _toggle_live_dim(self) -> None:
        """Swap the embedded live view between the 2D current-layer plot and
        an isometric 3D view of the whole toolpath. Matplotlib can't change an
        existing Axes' projection in place, so the figure is cleared and a
        fresh Axes is added; that forces `_sync_live_view` to redraw from
        scratch (`_live_tp` reset)."""
        self.live_3d = not self.live_3d
        self.live_fig.clf()
        if self.live_3d:
            self.live_ax = self.live_fig.add_subplot(1, 1, 1, projection="3d")
            self.btn_live_dim.configure(text="2D view")
        else:
            self.live_ax = self.live_fig.add_subplot(1, 1, 1)
            self.btn_live_dim.configure(text="3D view")
        self._live_tp = None
        self._live_layer = -1
        self._live_art = {}
        self._sync_live_view()

    def _sync_live_view(self) -> None:
        """Redraw the embedded live-print canvas: the active layer's toolpath
        (or, in 3D mode, the whole part) plus a marker at the nozzle position
        implied by how far the run has streamed (`Controller.progress_point` -
        derived from line progress against the parsed toolpath, no extra
        printer traffic). Static (just the loaded file, no marker) before/after
        a run."""
        tp = self.c.toolpath
        if tp is None:
            return
        if tp is not self._live_tp:
            self._live_tp = tp
            self._live_layer = -1
            self._live_art = {}
        current_line, total = self.c.progress

        if self.live_3d:
            if not self._live_art:
                self._live_art = tf.draw_live_3d(self.live_ax, tp)
                self.live_fig.tight_layout()
            if total:
                tf.update_live_marker_3d(self._live_art, tp.progress_position(current_line))
        else:
            layer = tp.progress_layer(current_line) if total else 0
            if layer != self._live_layer:
                self._live_layer = layer
                self._live_art = tf.draw_live_layer(self.live_ax, tp, layer)
                self.live_fig.tight_layout()
            if total:
                tf.update_live_marker(self._live_art, tp.progress_position(current_line))
        self.live_canvas.draw_idle()

        text = self.c.current_line_text.strip()
        self.live_line_lbl.configure(
            text=f"current step (line {current_line}/{total}): {text or '(comment/blank)'}"
            if total else "current step: not running"
        )

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
            and self._tick % self._idle_poll_ticks == 0
        ):
            self.c.refresh_state()  # safe during a run too - see Controller.refresh_state

        if (
            self._live_view_ticks
            and self.c.toolpath is not None
            and self._tick % self._live_view_ticks == 0
        ):
            self._sync_live_view()

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
        self.noz_now.configure(text=f"now: {st.nozzle_temp:.0f}/{st.nozzle_target:.0f}°C")
        self.bed_now.configure(text=f"now: {st.bed_temp:.0f}/{st.bed_target:.0f}°C")

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
        self.btn_level.configure(state=idle_state)
        self.btn_zcal.configure(state=idle_state)
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
    root.geometry("640x800")
    root.minsize(480, 360)
    panel = ControlPanel(root, controller)
    panel.pack(fill="both", expand=True)
    root.mainloop()
