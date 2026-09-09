"""'Plan magnet insert' dialog — place the sentinel and save `*.magnet.gcode` (C17).

The pure helpers (`resolve_target_z`, `magnet_output_path`, `save_magnet_gcode`,
`envelope_report`) carry the logic and are unit-tested without Tk. `PlanInsertDialog`
is a thin view over them.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..gcode.postprocess import inject_sentinel
from ..gcode.toolpath import Toolpath, parse_toolpath
from ..sequences.geometry import check_envelope
from ..state import SHEAR_DIRS, MagnetInsert
from ..viz import toolpath_fig as tf


# --- pure helpers --------------------------------------------------------

def resolve_target_z(mode: str, value: float, toolpath: Toolpath) -> float:
    """`mode == "layer"` -> the height of that layer index; `"z"` -> `value` as-is."""
    if mode == "layer":
        i = max(0, min(int(value), toolpath.layer_count - 1))
        return toolpath.layer_z[i]
    return float(value)


def magnet_output_path(in_path: str | Path) -> Path:
    p = Path(in_path)
    return p.with_suffix(".magnet" + p.suffix)


def save_magnet_gcode(
    in_path: str | Path,
    mi: MagnetInsert,
    target_z: float,
    *,
    emit_pause: bool = False,
) -> Path:
    """Write `<stem>.magnet.gcode` next to `in_path` and return its path."""
    out = magnet_output_path(in_path)
    inject_sentinel(
        in_path, out,
        pocket_xy=mi.pocket_xy, seat_z=mi.seat_z, shear=mi.shear_dir,
        z_mm=target_z, emit_pause=emit_pause,
    )
    return out


def envelope_report(mi: MagnetInsert, config: dict, toolpath: Toolpath) -> list[str]:
    """Envelope check using the printer state approximated at the seat height."""
    saved = tf.state_at_z(toolpath, mi.seat_z)
    return check_envelope(mi, config, saved)


# --- dialog ------------------------------------------------------------

class PlanInsertDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, controller) -> None:
        super().__init__(master)
        self.title("Plan magnet insert")
        self.resizable(False, False)
        self.c = controller
        self.in_path = Path(controller.gcode_path)
        self.tp = parse_toolpath(self.in_path)

        top_layer = self.tp.layer_count - 1
        cx = round(sum(v for v in (self.tp.bbox_min[0], self.tp.bbox_max[0])) / 2, 1)
        cy = round(sum(v for v in (self.tp.bbox_min[1], self.tp.bbox_max[1])) / 2, 1)

        self.px = tk.StringVar(value=str(cx))
        self.py = tk.StringVar(value=str(cy))
        self.sz = tk.StringVar(value=f"{self.tp.top_z:.2f}")
        self.shear = tk.StringVar(value=SHEAR_DIRS[0])
        self.mode = tk.StringVar(value="layer")
        self.tgt = tk.StringVar(value=str(max(0, top_layer - 1)))
        self.pause = tk.BooleanVar(value=False)

        self._build()
        self._check()

    def _build(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"file: {self.in_path.name}   "
                            f"{self.tp.layer_count} layers, top Z {self.tp.top_z:.2f} mm"
                  ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        def field(r, label, var, width=8):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=2)
            e = ttk.Entry(frm, textvariable=var, width=width)
            e.grid(row=r, column=1, sticky="w", pady=2)
            e.bind("<KeyRelease>", lambda _e: self._check())
            return e

        field(1, "pocket X (mm)", self.px)
        field(2, "pocket Y (mm)", self.py)
        field(3, "seat Z (mm)", self.sz)

        ttk.Label(frm, text="shear").grid(row=4, column=0, sticky="e", padx=(0, 6))
        ttk.Combobox(frm, textvariable=self.shear, values=list(SHEAR_DIRS),
                     width=5, state="readonly").grid(row=4, column=1, sticky="w")

        tgtfrm = ttk.LabelFrame(frm, text="insert at", padding=6)
        tgtfrm.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        ttk.Radiobutton(tgtfrm, text="layer index", variable=self.mode, value="layer",
                        command=self._check).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(tgtfrm, text="Z height (mm)", variable=self.mode, value="z",
                        command=self._check).grid(row=1, column=0, sticky="w")
        e = ttk.Entry(tgtfrm, textvariable=self.tgt, width=8)
        e.grid(row=0, column=1, rowspan=2, padx=8)
        e.bind("<KeyRelease>", lambda _e: self._check())

        ttk.Checkbutton(frm, text="also write a real M0 (pause on microSD prints)",
                        variable=self.pause).grid(row=6, column=0, columnspan=4, sticky="w", pady=4)

        self.status = ttk.Label(frm, text="", wraplength=320)
        self.status.grid(row=7, column=0, columnspan=4, sticky="w", pady=(6, 8))

        bar = ttk.Frame(frm)
        bar.grid(row=8, column=0, columnspan=4, sticky="e")
        ttk.Button(bar, text="Preview", command=self._preview).pack(side="left", padx=4)
        self.btn_save = ttk.Button(bar, text="Save .magnet.gcode", command=self._save)
        self.btn_save.pack(side="left", padx=4)
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="left", padx=4)

    def _mi(self) -> MagnetInsert:
        return MagnetInsert(
            pocket_x=float(self.px.get()), pocket_y=float(self.py.get()),
            seat_z=float(self.sz.get()), shear_dir=self.shear.get(),
        )

    def _check(self) -> MagnetInsert | None:
        try:
            mi = self._mi()
            target_z = resolve_target_z(self.mode.get(), float(self.tgt.get()), self.tp)
        except (ValueError, KeyError) as exc:
            self.status.configure(text=f"invalid input: {exc}", foreground="#c23a3a")
            self.btn_save.configure(state="disabled")
            return None
        bad = envelope_report(mi, self.c.config, self.tp)
        if bad:
            self.status.configure(text="OUT OF ENVELOPE — " + "; ".join(bad),
                                  foreground="#c23a3a")
            self.btn_save.configure(state="disabled")
            return None
        self.status.configure(
            text=f"OK — sentinel goes in near Z {target_z:.2f} mm "
                 f"(layer {self.tp.layer_for_z(target_z)})",
            foreground="#1f8a5f",
        )
        self.btn_save.configure(state="normal")
        return mi

    def _preview(self) -> None:
        mi = self._check()
        if mi is None:
            return
        from ..viz.preview import open_preview
        open_preview(self, self.tp, mi, self.c.config)

    def _save(self) -> None:
        mi = self._check()
        if mi is None:
            return
        target_z = resolve_target_z(self.mode.get(), float(self.tgt.get()), self.tp)
        try:
            out = save_magnet_gcode(self.in_path, mi, target_z,
                                    emit_pause=bool(self.pause.get()))
        except Exception as exc:  # noqa: BLE001 - surface any postprocess failure
            messagebox.showerror("Could not save", str(exc))
            return
        self.c.load_gcode(out)
        messagebox.showinfo("Saved", f"Wrote {out.name}\nLoaded as the active file.")
        self.destroy()
