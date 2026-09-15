"""C19 end-to-end: raw slice -> toolpath -> plan -> inject -> stream -> insert -> success.

One test that exercises the whole bring-your-own-G-code workflow on the sims.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from magnet_embed import entry
from magnet_embed.gcode.sentinel import parse_sentinel
from magnet_embed.gcode.toolpath import parse_toolpath
from magnet_embed.sequences.geometry import check_envelope, plan_insert_moves
from magnet_embed.state import MagnetInsert
from magnet_embed.ui.plan_dialog import save_magnet_gcode
from magnet_embed.viz import toolpath_fig as tf

DATA = Path(__file__).parent / "data"


def test_full_bring_your_own_gcode_workflow(config, tmp_path):
    # pole 25 mm to the -X of the nozzle: the cura coupon spans X 0..50, so a
    # pocket at X30 puts the nozzle at X55 - clear of the part (C25 guard)
    cfg = {**config, "magnet_tool_offset": {"x": -25.0, "y": 0.0, "z": 2.0}}

    # 1. the operator brings a finished slice
    raw = tmp_path / "coupon.gcode"
    shutil.copy(DATA / "cura_sample.gcode", raw)

    # 2. visualise it
    tp = parse_toolpath(raw)
    assert tp.layer_count == 5

    # 3. plan the insert; the damage guard must be clear
    mi = MagnetInsert(pocket_x=30.0, pocket_y=30.0, seat_z=6.0, shear_dir="+X")
    saved = tf.state_at_z(tp, mi.seat_z)
    assert check_envelope(mi, cfg, saved, tp) == []
    assert len(plan_insert_moves(mi, cfg, saved)) == 8

    # 4. save the annotated file
    out = save_magnet_gcode(raw, mi, target_z=6.0)
    assert out.name == "coupon.magnet.gcode"
    sentinel_line = next(
        ln for ln in out.read_text().splitlines() if ln.startswith(";MAGNET_INSERT")
    )
    assert parse_sentinel(sentinel_line) is not None

    # 5. stream it through the sim; the sentinel fires the insert; confirm success
    printer, dispenser = entry.build_links("sim", cfg, command_delay=0.0)
    assert entry.run_headless(printer, dispenser, cfg, out, confirm="success") == 0
    assert dispenser.count == 1                       # the insert sequence ran

    # 6. the print streamed to its end after resuming
    st = printer.query_state()
    assert (round(st.x, 1), round(st.y, 1)) == (50.0, 50.0)   # cura_sample's last move


def test_workflow_aborts_cleanly_on_out_of_envelope(config, tmp_path):
    cfg = {**config, "magnet_tool_offset": {"x": 5.0, "y": 0.0, "z": 2.0}}
    raw = tmp_path / "coupon.gcode"
    shutil.copy(DATA / "cura_sample.gcode", raw)
    # pocket hard against the bed edge -> approach X goes negative
    mi = MagnetInsert(pocket_x=2.0, pocket_y=30.0, seat_z=6.0, shear_dir="-X")
    out = save_magnet_gcode(raw, mi, target_z=6.0)

    printer, dispenser = entry.build_links("sim", cfg, command_delay=0.0)
    assert entry.run_headless(printer, dispenser, cfg, out, confirm="success") == 1
    assert dispenser.count == 0                       # aborted before dispensing


def test_workflow_aborts_on_nozzle_vs_part_collision(config, tmp_path):
    """C25: a pocket in the middle of the part with a pole-above-nozzle offset
    would drive the nozzle into the print - refused before any motion, headless
    too (run_headless parses the toolpath for the guard itself)."""
    cfg = {**config, "magnet_tool_offset": {"x": 5.0, "y": 0.0, "z": 2.0}}
    raw = tmp_path / "coupon.gcode"
    shutil.copy(DATA / "cura_sample.gcode", raw)
    mi = MagnetInsert(pocket_x=30.0, pocket_y=30.0, seat_z=6.0, shear_dir="+X")
    tp = parse_toolpath(raw)
    bad = check_envelope(mi, cfg, tf.state_at_z(tp, mi.seat_z), tp)
    assert any("printed part" in b for b in bad)
    out = save_magnet_gcode(raw, mi, target_z=6.0)

    printer, dispenser = entry.build_links("sim", cfg, command_delay=0.0)
    assert entry.run_headless(printer, dispenser, cfg, out, confirm="success") == 1
    assert dispenser.count == 0
