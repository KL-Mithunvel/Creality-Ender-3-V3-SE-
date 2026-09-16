"""'Settings' dialog - edit the machine-local config values from the panel.

`build_updates` carries the parsing/validation and is unit-tested without Tk;
`SettingsDialog` is a thin view over it and `config.save_local_override`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..config import load_config, save_local_override


def build_updates(
    *,
    printer_port: str,
    dispenser_port: str,
    offset_x: str,
    offset_y: str,
    offset_z: str,
) -> dict:
    """Parse the dialog's fields into a `config.local.yaml`-shaped update dict.

    Raises `ValueError` on a non-numeric offset (the ports are free text)."""
    return {
        "printer": {"port": printer_port.strip()},
        "dispenser": {"port": dispenser_port.strip()},
        "magnet_tool_offset": {
            "x": float(offset_x),
            "y": float(offset_y),
            "z": float(offset_z),
        },
    }


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, controller) -> None:
        super().__init__(master)
        self.title("Settings")
        self.resizable(False, False)
        self.c = controller

        cfg = controller.config
        off = cfg["magnet_tool_offset"]
        self.printer_port = tk.StringVar(value=str(cfg["printer"]["port"]))
        self.dispenser_port = tk.StringVar(value=str(cfg["dispenser"]["port"]))
        self.off_x = tk.StringVar(value=str(off["x"]))
        self.off_y = tk.StringVar(value=str(off["y"]))
        self.off_z = tk.StringVar(value=str(off["z"]))

        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="Machine-local settings - written to config.local.yaml, "
                 "never the committed config.yaml.",
            wraplength=340,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        def field(r: int, label: str, var: tk.StringVar, width: int = 14) -> None:
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=2)
            ttk.Entry(frm, textvariable=var, width=width).grid(row=r, column=1, sticky="w", pady=2)

        field(1, "printer port", self.printer_port)
        field(2, "dispenser port", self.dispenser_port)
        field(3, "magnet offset X (mm)", self.off_x)
        field(4, "magnet offset Y (mm)", self.off_y)
        field(5, "magnet offset Z (mm)", self.off_z)

        ttk.Label(
            frm,
            text="Port changes need an app restart to take effect. "
                 "Offset changes apply to the very next magnet insert.",
            foreground="gray",
            wraplength=340,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 8))

        self.status = ttk.Label(frm, text="", wraplength=340, foreground="#c23a3a")
        self.status.grid(row=7, column=0, columnspan=2, sticky="w")

        bar = ttk.Frame(frm)
        bar.grid(row=8, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left", padx=4)
        ttk.Button(bar, text="Close", command=self.destroy).pack(side="left", padx=4)

    def _save(self) -> None:
        try:
            updates = build_updates(
                printer_port=self.printer_port.get(),
                dispenser_port=self.dispenser_port.get(),
                offset_x=self.off_x.get(),
                offset_y=self.off_y.get(),
                offset_z=self.off_z.get(),
            )
        except ValueError as exc:
            self.status.configure(text=f"invalid input: {exc}")
            return
        save_local_override(updates)
        self.c.config = load_config()
        messagebox.showinfo(
            "Saved",
            "Wrote config.local.yaml.\n"
            "Offset changes apply immediately; port changes need an app restart.",
        )
        self.destroy()
