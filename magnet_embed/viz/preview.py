"""Tkinter preview window — toolpath + animated magnet-insert motion (C16).

Two 2D panels (top X–Y, side X–Z) with a layer slider; when a `MagnetInsert` is
given, the phase-coloured insert path is overlaid and the nozzle + pole tip animate
along it (play / scrub). "Open 3D view" pops a rotatable 3D toolpath.

Import this module lazily — it pulls in matplotlib.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers the 3d projection)

from ..gcode.toolpath import Toolpath
from ..sequences.geometry import check_envelope
from ..state import MagnetInsert
from . import toolpath_fig as tf

_TICK_MS = 40
_DURATION_S = 8.0


class PreviewWindow(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        toolpath: Toolpath,
        mi: MagnetInsert | None = None,
        config: dict | None = None,
        saved=None,
    ) -> None:
        super().__init__(master)
        self.title("Toolpath preview" if mi is None else "Magnet insert preview")
        self.tp = toolpath
        self.mi = mi
        self.cfg = config or {}
        self.saved = saved
        self.moves: list = []
        self.bad: list[str] = []
        if mi is not None:
            if self.saved is None:
                self.saved = tf.state_at_z(toolpath, mi.seat_z)
            self.moves = tf.plan_for(mi, self.cfg, self.saved)
            self.bad = check_envelope(mi, self.cfg, self.saved)

        start_layer = toolpath.layer_for_z(mi.seat_z) if mi else 0
        self.layer = tk.IntVar(value=start_layer)
        self.t = tk.DoubleVar(value=0.0)
        self.playing = False
        self._art_xy: dict = {}
        self._art_xz: dict = {}

        self.fig = Figure(figsize=(9.2, 4.3), dpi=100)
        self.ax_xy = self.fig.add_subplot(1, 2, 1)
        self.ax_xz = self.fig.add_subplot(1, 2, 2)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self._build_controls()
        self._redraw_static()
        self.after(_TICK_MS, self._tick)

    # --- layout --------------------------------------------------------

    def _build_controls(self) -> None:
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Label(bar, text="layer").pack(side="left")
        ttk.Scale(
            bar, from_=0, to=max(0, self.tp.layer_count - 1), variable=self.layer,
            command=lambda _v: self._on_layer(),
        ).pack(side="left", fill="x", expand=True, padx=6)
        self.layer_lbl = ttk.Label(bar, width=20)
        self.layer_lbl.pack(side="left")

        if self.mi is not None:
            play = ttk.Frame(self, padding=(6, 0, 6, 6))
            play.pack(fill="x")
            self.btn_play = ttk.Button(play, text="Play", command=self._toggle_play)
            self.btn_play.pack(side="left")
            ttk.Scale(
                play, from_=0.0, to=1.0, variable=self.t,
                command=lambda _v: self._on_scrub(),
            ).pack(side="left", fill="x", expand=True, padx=6)
            self.phase_lbl = ttk.Label(play, width=24)
            self.phase_lbl.pack(side="left")
            if self.bad:
                ttk.Label(
                    self, text="OUT OF ENVELOPE — " + "; ".join(self.bad),
                    foreground="#c23a3a", padding=(6, 0, 6, 6),
                ).pack(fill="x")

        ttk.Button(self, text="Open 3D view", command=self._open_3d).pack(
            anchor="w", padx=6, pady=(0, 6)
        )

    # --- drawing ------------------------------------------------------

    def _redraw_static(self) -> None:
        li = int(self.layer.get())
        li = max(0, min(li, self.tp.layer_count - 1))
        tf.draw_layer_xy(self.ax_xy, self.tp, li)
        tf.draw_side_xz(self.ax_xz, self.tp)
        if self.mi is not None:
            self._art_xy = tf.draw_insert_overlay(
                self.ax_xy, self.moves, self.saved, self.cfg, plane="xy"
            )
            self._art_xz = tf.draw_insert_overlay(
                self.ax_xz, self.moves, self.saved, self.cfg, plane="xz"
            )
            self.ax_xy.plot(
                [self.mi.pocket_x], [self.mi.pocket_y], "x",
                color=tf.PHASE_COLOR["RESUME"], ms=9, mew=2,
            )
        self.layer_lbl.configure(
            text=f"Z {self.tp.layer_z[li]:.2f} / {self.tp.top_z:.2f} mm"
        )
        self.fig.tight_layout()
        self.canvas.draw_idle()
        if self.mi is not None:
            self._apply_t()

    def _apply_t(self) -> None:
        if not self._art_xy:
            return
        tval = float(self.t.get())
        seg = tf.update_insert_marker(self._art_xy, tval, "xy")
        tf.update_insert_marker(self._art_xz, tval, "xz")
        phase = self.moves[min(seg, len(self.moves) - 1)].phase
        self.phase_lbl.configure(text=f"{phase}   {tval:.0%}")
        self.canvas.draw_idle()

    # --- controls ---------------------------------------------------

    def _on_layer(self) -> None:
        self._redraw_static()

    def _toggle_play(self) -> None:
        if float(self.t.get()) >= 1.0:
            self.t.set(0.0)
        self.playing = not self.playing
        self.btn_play.configure(text="Pause" if self.playing else "Play")

    def _on_scrub(self) -> None:
        self.playing = False
        self.btn_play.configure(text="Play")
        self._apply_t()

    def _tick(self) -> None:
        if self.playing:
            nt = float(self.t.get()) + _TICK_MS / 1000.0 / _DURATION_S
            if nt >= 1.0:
                nt, self.playing = 1.0, False
                self.btn_play.configure(text="Replay")
            self.t.set(nt)
            self._apply_t()
        self.after(_TICK_MS, self._tick)

    def _open_3d(self) -> None:
        win = tk.Toplevel(self)
        win.title("3D toolpath")
        fig = Figure(figsize=(6, 6), dpi=100)
        ax = fig.add_subplot(1, 1, 1, projection="3d")
        tf.draw_path_3d(ax, self.tp)
        if self.mi is not None:
            noz = tf.nozzle_waypoints(self.moves, self.saved)
            pol = tf.pole_waypoints(self.moves, self.saved, self.cfg)
            for i, ph in enumerate(tf.phase_labels(self.moves)):
                a, b = noz[i], noz[i + 1]
                ax.plot([a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                        color=tf.PHASE_COLOR.get(ph, "#888"), lw=2.5)
            ax.plot([p[0] for p in pol], [p[1] for p in pol], [p[2] for p in pol],
                    color=tf.PHASE_COLOR["RESUME"], lw=1.0, ls="--", alpha=0.6)
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        canvas.draw()


def open_preview(master, toolpath, mi=None, config=None, saved=None) -> PreviewWindow:
    return PreviewWindow(master, toolpath, mi, config, saved)
