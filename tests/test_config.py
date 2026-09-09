from magnet_embed.config import _deep_merge, load_config


def test_deep_merge_recurses_and_does_not_mutate():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    over = {"a": {"y": 20, "z": 30}, "c": 4}
    out = _deep_merge(base, over)
    assert out == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3, "c": 4}
    assert base["a"]["y"] == 2  # original untouched


def test_load_defaults():
    cfg = load_config()
    assert cfg["printer"]["baud"] == 115200
    assert cfg["printer"]["ack_timeout_s"] == 30
    assert cfg["gcode"]["sentinel_token"] == ";MAGNET_INSERT"
    assert cfg["machine"]["x_max"] == 220


def test_local_override_is_merged(tmp_path):
    base = tmp_path / "config.yaml"
    base.write_text(
        "printer: {port: COM3, baud: 115200, ack_timeout_s: 30}\n"
        "dispenser: {port: COM4, baud: 115200}\n"
        "machine: {x_max: 220, y_max: 220, z_max: 250}\n"
        "magnet_tool_offset: {x: 1, y: 2, z: 3}\n"
        "park: {x: 5, y: 5, safe_z_lift_mm: 15}\n"
        "temps: {standby_nozzle_c: 160}\n"
        "press: {feed: 60, dwell_ms: 500}\n"
        "shear: {distance: 5, feed: 1200}\n"
        "gcode: {sentinel_token: ';MAGNET_INSERT'}\n",
        encoding="utf-8",
    )
    (tmp_path / "config.local.yaml").write_text(
        "printer: {port: COM9}\nmagnet_tool_offset: {x: 31.5}\n", encoding="utf-8"
    )
    cfg = load_config(base)
    assert cfg["printer"]["port"] == "COM9"        # overridden
    assert cfg["printer"]["baud"] == 115200        # kept
    assert cfg["magnet_tool_offset"]["x"] == 31.5  # overridden
    assert cfg["magnet_tool_offset"]["y"] == 2     # kept


def test_missing_required_key_raises(tmp_path):
    import pytest

    base = tmp_path / "config.yaml"
    base.write_text("printer: {port: COM3}\n", encoding="utf-8")
    with pytest.raises(KeyError):
        load_config(base)
