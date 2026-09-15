import yaml

from magnet_embed.config import _deep_merge, load_config, save_local_override


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
        "travel: {feed: 6000}\n"
        "temps: {standby_nozzle_c: 160, nozzle_min_c: 0, nozzle_max_c: 260, "
        "bed_min_c: 0, bed_max_c: 100}\n"
        "retract: {mm: 3, feed: 2400}\n"
        "prime: {mm: 2, feed: 300}\n"
        "press: {feed: 60, dwell_ms: 500}\n"
        "shear: {distance: 5, feed: 1200}\n"
        "collision: {nozzle_clearance_mm: 1.0, footprint_margin_mm: 2.0}\n"
        "gcode: {sentinel_token: ';MAGNET_INSERT'}\n"
        "zcal: {x: 110, y: 110, start_z: 5, step_mm: 0.05, feed: 100, probe_z_offset: 0}\n",
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


def test_ui_idle_poll_default_present():
    assert load_config()["ui"]["idle_poll_s"] == 2.0


def test_validate_rejects_bad_idle_poll():
    import pytest

    from magnet_embed.config import _validate

    cfg = load_config()
    cfg["ui"]["idle_poll_s"] = -1
    with pytest.raises(ValueError):
        _validate(cfg)
    cfg["ui"]["idle_poll_s"] = "fast"
    with pytest.raises(ValueError):
        _validate(cfg)


def test_ui_live_view_poll_default_present():
    assert load_config()["ui"]["live_view_poll_s"] == 0.15


def test_validate_rejects_bad_live_view_poll():
    import pytest

    from magnet_embed.config import _validate

    cfg = load_config()
    cfg["ui"]["live_view_poll_s"] = -1
    with pytest.raises(ValueError):
        _validate(cfg)
    cfg["ui"]["live_view_poll_s"] = "fast"
    with pytest.raises(ValueError):
        _validate(cfg)


def test_zcal_defaults_present():
    cfg = load_config()
    assert cfg["zcal"]["probe_z_offset"] == 0.0
    assert cfg["zcal"]["step_mm"] > 0


def test_validate_rejects_non_numeric_zcal_field():
    import pytest

    from magnet_embed.config import _validate

    cfg = load_config()
    cfg["zcal"]["feed"] = "fast"
    with pytest.raises(ValueError):
        _validate(cfg)


def test_collision_defaults_present():
    cfg = load_config()
    assert cfg["collision"]["nozzle_clearance_mm"] > 0
    assert cfg["collision"]["footprint_margin_mm"] >= 0


def test_validate_rejects_non_numeric_collision_field():
    import pytest

    from magnet_embed.config import _validate

    cfg = load_config()
    cfg["collision"]["nozzle_clearance_mm"] = "some"
    with pytest.raises(ValueError):
        _validate(cfg)


def test_temp_range_defaults_present():
    cfg = load_config()
    assert cfg["temps"]["nozzle_min_c"] < cfg["temps"]["nozzle_max_c"]
    assert cfg["temps"]["bed_min_c"] < cfg["temps"]["bed_max_c"]


def test_validate_rejects_bad_temp_range():
    import pytest

    from magnet_embed.config import _validate

    cfg = load_config()
    cfg["temps"]["nozzle_min_c"] = cfg["temps"]["nozzle_max_c"]
    with pytest.raises(ValueError):
        _validate(cfg)

    cfg = load_config()
    cfg["temps"]["bed_min_c"] = cfg["temps"]["bed_max_c"] + 1
    with pytest.raises(ValueError):
        _validate(cfg)


# --- save_local_override (Settings dialog) ---------------------------

def test_save_local_override_creates_file(tmp_path):
    base = tmp_path / "config.yaml"
    base.write_text("printer: {port: COM3}\n", encoding="utf-8")
    merged = save_local_override({"printer": {"port": "COM9"}}, base)
    assert merged["printer"]["port"] == "COM9"

    local = tmp_path / "config.local.yaml"
    assert local.exists()
    assert yaml.safe_load(local.read_text())["printer"]["port"] == "COM9"


def test_save_local_override_merges_with_existing(tmp_path):
    base = tmp_path / "config.yaml"
    base.write_text("printer: {port: COM3}\n", encoding="utf-8")
    local = tmp_path / "config.local.yaml"
    local.write_text("printer: {port: COM9}\nmagnet_tool_offset: {x: 1}\n", encoding="utf-8")

    save_local_override({"magnet_tool_offset": {"y": 2}}, base)

    data = yaml.safe_load(local.read_text())
    assert data["printer"]["port"] == "COM9"          # untouched
    assert data["magnet_tool_offset"] == {"x": 1, "y": 2}
