"""Tkinter control panel.

Thin view over `magnet_embed.app.Controller`: buttons call the controller's
action methods; a 120 ms timer drains `controller.poll_events()` and updates the
widgets. All Tkinter work stays on the main thread.

Two-column layout (C24): the top bar/files/run/progress rows span the full
width; below that, jog/home + temperature + filament sit in a left column and
the live-print view + send-G-code + log sit in a right column that expands to
fill whatever width/height the window has - `run_gui()` opens maximized by
default. The whole thing still lives inside a scrollable canvas
(`_build_scroll_container`) as a fallback for a screen too small to fit
everything even maximized; the canvas now also stretches `self.body` to fill
any *extra* height so the weighted rows (the live view, the log) actually grow
into it instead of leaving blank space.

Embeds a small live-print view (`_sync_live_view`) driven off
`Controller.toolpath` / `progress_point` - derived from G-code line progress
against the parsed toolpath, so it costs no extra printer traffic and never
contends with the streaming loop's own serial handshake. Two panels side by
side, always both visible: the current layer in 2D, and an isometric 3D view
with a path that grows as the nozzle actually passes through it
(`viz.toolpath_fig.draw_live_3d`/`update_live_3d`) - a "Global bed / Local
part" toggle swaps the 3D view between the whole bed (real scale, real
context) and a tight crop around just the part (fills the view, easier to
actually see on a short/flat print) - plus a current-step G-code text line
under both.
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
        self._live_art2d: dict = {}
        self._live_art3d: dict = {}
        self._insert_phase: str | None = None
        self._insert_position: tuple[float, float, float] | None = None
        self.live3d_global = True  # True = whole bed ("Global"), False = zoomed to the part ("Local")
        self._build_scroll_container()
        self._build()
        self.after(_POLL_MS, self._poll)

    # --- scrolling shell --------------------------------------------

    def _build_scroll_container(self) -> None:
        """Wrap the whole panel in a Canvas + Scrollbar so tall content never
        gets clipped by a screen shorter than the panel's natural height - it
        scrolls instead. The canvas window is stretched to at least the
        canvas's own visible height (never less than the body's natural
        height) so a maximized window's extra space actually reaches the
        weighted rows inside `self.body` (the live view, the log) instead of
        leaving blank space below a short, un-stretched body."""
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

        def _on_canvas_configure(event: tk.Event) -> None:
            req_h = self.body.winfo_reqheight()
            canvas.itemconfigure(window, width=event.width, height=max(event.height, req_h))

        canvas.bind("<Configure>", _on_canvas_configure)

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
        top.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.btn_connect = ttk.Button(top, text="Connect", command=self._toggle_connect)
        self.btn_connect.pack(side="left")
        self.status = ttk.Label(top, text="not connected")
        self.status.pack(side="left", padx=8)
        self.target_lbl = ttk.Label(top, text=f"({self.c.link_summary})", foreground="gray")
        self.target_lbl.pack(side="left")
        ttk.Button(top, text="Settings…", command=self._open_settings).pack(side="left", padx=(12, 0))
        # Emergency stop: always enabled, never confirmed, bypasses the idle
        # guard and the printer lock (`Controller.emergency_stop`). A plain
        # tk.Button, not ttk - the Windows ttk theme ignores background colours
        # and this one has to be unmistakably red.
        self.btn_estop = tk.Button(
            top, text="EMERGENCY STOP", command=self.c.emergency_stop,
            bg="#c62828", fg="white", activebackground="#8e0000", activeforeground="white",
            font=("TkDefaultFont", 10, "bold"), relief="raised", bd=2, padx=12, pady=2,
            cursor="hand2",
        )
        self.btn_estop.pack(side="right")
        row += 1

        files = ttk.Frame(b)
        files.grid(row=row, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Button(files, text="Load G-code…", command=self._load).pack(side="left")
        self.btn_plan = ttk.Button(files, text="Plan magnet insert…", command=self._plan_insert)
        self.btn_plan.pack(side="left", padx=6)
        self.file_lbl = ttk.Label(files, text="(no file)")
        self.file_lbl.pack(side="left", padx=8)
        row += 1

        run = ttk.Frame(b)
        run.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4)
        self.btn_run = ttk.Button(run, text="Run", command=self.c.start_run)
        self.btn_pause = ttk.Button(run, text="Pause", command=self.c.pause)
        self.btn_resume = ttk.Button(run, text="Resume", command=self.c.resume)
        self.btn_cancel = ttk.Button(run, text="Cancel", command=self.c.cancel)
        for btn in (self.btn_run, self.btn_pause, self.btn_resume, self.btn_cancel):
            btn.pack(side="left", padx=2)
        row += 1

        prog = ttk.Frame(b)
        prog.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self.progressbar = ttk.Progressbar(prog, mode="determinate")
        self.progressbar.pack(side="left", fill="x", expand=True)
        self.prog_lbl = ttk.Label(prog, text="—", width=20)
        self.prog_lbl.pack(side="left", padx=6)
        row += 1

        content_row = row
        b.columnconfigure(0, weight=0)
        b.columnconfigure(1, weight=1)
        b.rowconfigure(content_row, weight=1)

        left = ttk.Frame(b)
        left.grid(row=content_row, column=0, sticky="nw", padx=(0, 8))
        right = ttk.Frame(b)
        right.grid(row=content_row, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, left: ttk.Frame) -> None:
        """Jog/home, temperature, filament - the compact controls column."""
        lrow = 0

        jog = ttk.LabelFrame(left, text="Jog / home  (idle only)", padding=6)
        jog.grid(row=lrow, column=0, sticky="ew", pady=4)
        lrow += 1
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

        temp = ttk.LabelFrame(left, text="Temperature  (works during a print too)", padding=6)
        temp.grid(row=lrow, column=0, sticky="ew", pady=4)
        lrow += 1
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

        fil = ttk.LabelFrame(left, text="Filament  (idle only)", padding=6)
        fil.grid(row=lrow, column=0, sticky="ew", pady=4)
        lrow += 1
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

    def _build_right(self, right: ttk.Frame) -> None:
        """Live-print view (2D + 3D side by side), send-G-code, state, log -
        the column that expands to fill a maximized window."""
        rrow = 0

        live = ttk.LabelFrame(right, text="Live print view", padding=4)
        live.grid(row=rrow, column=0, sticky="nsew", pady=(0, 4))
        right.rowconfigure(rrow, weight=3)
        rrow += 1
        live.columnconfigure(0, weight=1)
        live.rowconfigure(1, weight=1)

        live_hdr = ttk.Frame(live)
        live_hdr.grid(row=0, column=0, sticky="ew")
        ttk.Label(live_hdr, text="2D current layer  /  3D:").pack(side="left")
        self.btn_bed_view = ttk.Button(live_hdr, text="Global bed", width=10, command=self._toggle_bed_view)
        self.btn_bed_view.pack(side="left", padx=(4, 0))

        plots = ttk.Frame(live)
        plots.grid(row=1, column=0, sticky="nsew")
        plots.columnconfigure(0, weight=1)
        plots.columnconfigure(1, weight=1)
        plots.rowconfigure(0, weight=1)

        live2d = ttk.Frame(plots)
        live2d.grid(row=0, column=0, sticky="nsew")
        self.live2d_fig = Figure(figsize=(3.6, 3.0), dpi=90)
        self.live2d_ax = self.live2d_fig.add_subplot(1, 1, 1)
        self.live2d_canvas = FigureCanvasTkAgg(self.live2d_fig, master=live2d)
        self.live2d_canvas.get_tk_widget().pack(fill="both", expand=True)

        live3d = ttk.Frame(plots)
        live3d.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.live3d_fig = Figure(figsize=(3.6, 3.0), dpi=90)
        self.live3d_ax = self.live3d_fig.add_subplot(1, 1, 1, projection="3d")
        self.live3d_canvas = FigureCanvasTkAgg(self.live3d_fig, master=live3d)
        self.live3d_canvas.get_tk_widget().pack(fill="both", expand=True)

        self.live_line_lbl = ttk.Label(live, text="current step: —", anchor="w")
        self.live_line_lbl.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        cmd = ttk.LabelFrame(right, text="Send G-code  (idle only)", padding=6)
        cmd.grid(row=rrow, column=0, sticky="ew", pady=4)
        rrow += 1
        self.cmd_entry = ttk.Entry(cmd)
        self.cmd_entry.pack(side="left", fill="x", expand=True)
        self.cmd_entry.bind("<Return>", lambda _e: self._send_cmd())
        self.btn_send = ttk.Button(cmd, text="Send", command=self._send_cmd)
        self.btn_send.pack(side="left", padx=4)

        self.state_lbl = ttk.Label(right, text="position / temps: —")
        self.state_lbl.grid(row=rrow, column=0, sticky="w", pady=(4, 2))
        rrow += 1

        self.logbox = scrolledtext.ScrolledText(right, height=10, width=50, state="disabled")
        self.logbox.grid(row=rrow, column=0, sticky="nsew")
        right.rowconfigure(rrow, weight=1)

    # --- actions -------------------------------------------------

    def _toggle_connect(self) -> None:
        if self.c.connected:
            self.c.disconnect()
        else:
            self.c.connect()

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

    def _toggle_bed_view(self) -> None:
        """Swap the 3D view between the whole bed ("Global", real scale, real
        context) and a tight crop around just the part ("Local" - fills the
        view, much easier to actually see a short/flat print). Only the 3D
        artists need to be rebuilt; the 2D view and the loaded toolpath are
        unaffected."""
        self.live3d_global = not self.live3d_global
        self.btn_bed_view.configure(text="Global bed" if self.live3d_global else "Local part")
        self._live_art3d = {}
        self._sync_live_view()

    def _sync_live_view(self) -> None:
        """Redraw both embedded live-print canvases: the active layer in 2D
        (`live2d_*`) and the bed or part in 3D (`live3d_*`, per
        `live3d_global`), driven from `Controller.progress_point`/
        `current_line_text` - derived from line progress against the parsed
        toolpath, no extra printer traffic. The 2D layer redraws only when
        the active layer changes; the 3D path grows in place via
        `update_live_3d` rather than a full redraw. Static (no marker/path)
        before a run starts.

        While a magnet insert is running (`Controller.in_insert`), line
        progress is frozen at the sentinel - instead, the marker position and
        the "current step" label come from the latest `"phase"` event
        (`Controller._on_insert_phase`, fed by `insert_magnet`'s `on_phase`),
        and the 2D layer / 3D path stay frozen at whatever they were showing
        when the insert started, rather than being recomputed from line
        progress."""
        tp = self.c.toolpath
        if tp is None:
            return
        if tp is not self._live_tp:
            self._live_tp = tp
            self._live_layer = -1
            self._live_art2d = {}
            self._live_art3d = {}
        current_line, total = self.c.progress

        in_insert = self.c.in_insert and self._insert_phase is not None
        if not self.c.in_insert:
            self._insert_phase = None
            self._insert_position = None

        layer = self._live_layer if in_insert else (tp.progress_layer(current_line) if total else 0)
        if layer != self._live_layer:
            self._live_layer = layer
            self._live_art2d = tf.draw_live_layer(self.live2d_ax, tp, layer)
            self.live2d_fig.tight_layout()

        position = self._insert_position if in_insert else (
            tp.progress_position(current_line) if total else None
        )
        if position is not None:
            tf.update_live_marker(self._live_art2d, position)
        self.live2d_canvas.draw_idle()

        if not self._live_art3d:
            machine = self.c.config.get("machine", {})
            bed_xy = (machine.get("x_max", 220.0), machine.get("y_max", 220.0))
            self._live_art3d = tf.draw_live_3d(
                self.live3d_ax, tp, bed_xy, show_bed=self.live3d_global
            )
            self.live3d_fig.tight_layout()
        if in_insert:
            if position is not None:
                tf.update_live_3d_marker(self._live_art3d, position)
        elif total:
            tf.update_live_3d(self._live_art3d, tp, current_line)
        self.live3d_canvas.draw_idle()

        if in_insert:
            label = f"magnet insert in progress - phase: {self._insert_phase}"
        elif total:
            text = self.c.current_line_text.strip()
            label = f"current step (line {current_line}/{total}): {text or '(comment/blank)'}"
        else:
            label = "current step: not running"
        self.live_line_lbl.configure(text=label)

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
            elif kind == "phase":
                self._insert_phase = payload.get("phase")  # type: ignore[union-attr]
                self._insert_position = payload.get("position")  # type: ignore[union-attr]
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
        busy = running or self.c.busy    # busy (C27): Home/Level Bed/Z-cal in flight
        self.btn_connect.configure(
            text="Disconnect" if self.c.connected else "Connect",
            state=("disabled" if busy else "normal"),
        )
        self.btn_run.configure(
            state=("disabled" if busy or self.c.gcode_path is None else "normal")
        )
        for btn in (self.btn_pause, self.btn_resume, self.btn_cancel):
            btn.configure(state=("normal" if running else "disabled"))
        idle_state = "disabled" if busy else "normal"
        self.btn_send.configure(state=idle_state)
        self.cmd_entry.configure(state=idle_state)
        self.btn_extrude.configure(state=idle_state)
        self.btn_retract.configure(state=idle_state)
        self.btn_level.configure(state=idle_state)
        self.btn_zcal.configure(state=idle_state)
        self.btn_plan.configure(
            state=("disabled" if busy or self.c.gcode_path is None else "normal")
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
    root.minsize(760, 560)
    try:
        root.state("zoomed")  # open maximized (Windows) - fits everything at once
    except tk.TclError:
        root.geometry("1200x820")  # non-Windows fallback: a generous default, not maximized
    panel = ControlPanel(root, controller)
    panel.pack(fill="both", expand=True)
    root.mainloop()
