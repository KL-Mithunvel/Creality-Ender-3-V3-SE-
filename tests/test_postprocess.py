from pathlib import Path

import pytest

from magnet_embed.exceptions import PostprocessError
from magnet_embed.gcode.postprocess import inject_sentinel
from magnet_embed.gcode.sentinel import parse_sentinel

DATA = Path(__file__).parent / "data"
CURA = DATA / "cura_sample.gcode"
PRUSA = DATA / "prusa_sample.gcode"


def _run(src, tmp_path, **kw):
    out = tmp_path / "out.gcode"
    kw.setdefault("pocket_xy", (60.0, 55.0))
    kw.setdefault("seat_z", 6.0)
    kw.setdefault("shear", "+X")
    line_no = inject_sentinel(src, out, **kw)
    return out.read_text().splitlines(), line_no


def test_cura_inject_by_layer(tmp_path):
    lines, line_no = _run(CURA, tmp_path, layer=2)
    idx = lines.index(";LAYER:2")
    assert lines[idx + 1] == ";MAGNET_INSERT X60 Y55 Z6 S+X"
    assert line_no == idx + 2                       # 1-based
    # the sentinel round-trips through the parser
    mi = parse_sentinel(lines[idx + 1])
    assert mi.pocket_xy == (60.0, 55.0) and mi.shear_dir == "+X"


def test_cura_inject_by_height(tmp_path):
    lines, _ = _run(CURA, tmp_path, z_mm=4.0)      # layer 2 is at Z4.0
    idx = lines.index(";LAYER:2")
    assert lines[idx + 1].startswith(";MAGNET_INSERT")
    assert ";LAYER:3" in lines                     # rest of the file intact


def test_cura_height_between_layers_rounds_up(tmp_path):
    lines, _ = _run(CURA, tmp_path, z_mm=3.0)      # -> first layer with Z>=3 is layer 2 (Z4)
    idx = lines.index(";LAYER:2")
    assert lines[idx + 1].startswith(";MAGNET_INSERT")


def test_prusa_inject_by_ordinal(tmp_path):
    lines, _ = _run(PRUSA, tmp_path, layer=2)
    # 3rd LAYER_CHANGE block; sentinel goes right after its ;Z: line
    z_positions = [i for i, l in enumerate(lines) if l.strip() == ";Z:4"]
    assert lines[z_positions[0] + 1] == ";MAGNET_INSERT X60 Y55 Z6 S+X"


def test_prusa_inject_by_height(tmp_path):
    lines, _ = _run(PRUSA, tmp_path, z_mm=4.0)
    zi = lines.index(";Z:4")
    assert lines[zi + 1].startswith(";MAGNET_INSERT")


def test_exactly_one_sentinel_and_file_grows_by_one_line(tmp_path):
    src_lines = CURA.read_text().splitlines()
    lines, _ = _run(CURA, tmp_path, layer=1)
    assert sum(l.startswith(";MAGNET_INSERT") for l in lines) == 1
    assert len(lines) == len(src_lines) + 1


def test_no_markers_raises(tmp_path):
    plain = tmp_path / "plain.gcode"
    plain.write_text("G28\nG1 X10 Y10\n", encoding="utf-8")
    with pytest.raises(PostprocessError):
        inject_sentinel(plain, tmp_path / "o.gcode", pocket_xy=(1, 2), seat_z=3, shear="+X", layer=0)


def test_missing_layer_raises(tmp_path):
    with pytest.raises(PostprocessError):
        _run(CURA, tmp_path, layer=99)


def test_height_above_top_raises(tmp_path):
    with pytest.raises(PostprocessError):
        _run(CURA, tmp_path, z_mm=999.0)


def test_needs_exactly_one_of_layer_or_z(tmp_path):
    with pytest.raises(ValueError):
        _run(CURA, tmp_path)
    with pytest.raises(ValueError):
        _run(CURA, tmp_path, layer=1, z_mm=2.0)


def test_bad_shear_raises(tmp_path):
    with pytest.raises(ValueError):
        _run(CURA, tmp_path, layer=1, shear="+Q")


def test_cli(tmp_path, capsys):
    from magnet_embed.gcode.postprocess import main

    out = tmp_path / "cli_out.gcode"
    rc = main([str(CURA), "--layer", "2", "--xy", "60", "55", "--seat-z", "6", "--shear", "+X",
               "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert any(l.startswith(";MAGNET_INSERT") for l in out.read_text().splitlines())

    rc = main([str(CURA), "--layer", "99", "--xy", "1", "2", "--seat-z", "3", "--shear", "+X",
               "-o", str(tmp_path / "x.gcode")])
    assert rc == 1


def test_emit_pause_prepends_m0_before_the_sentinel(tmp_path):
    lines, line_no = _run(CURA, tmp_path, layer=2, emit_pause=True)
    idx = lines.index(";MAGNET_INSERT X60 Y55 Z6 S+X")
    assert lines[idx - 1].strip().startswith("M0")
    assert lines[idx - 2] == ";LAYER:2"
    assert line_no == idx + 1                       # 1-based line of the sentinel
