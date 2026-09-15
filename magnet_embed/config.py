"""Configuration loading: `config.yaml` + an optional git-ignored `config.local.yaml`.

`config.local.yaml` sits next to `config.yaml` and is deep-merged over it at load
time, so machine-specific values (real COM ports, the measured magnet-tool offset)
never touch the tracked file.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"

#: (section, key) pairs that must be present after merging.
_REQUIRED_KEYS: tuple[tuple[str, str], ...] = (
    ("printer", "port"),
    ("printer", "baud"),
    ("printer", "ack_timeout_s"),
    ("dispenser", "port"),
    ("dispenser", "baud"),
    ("machine", "x_max"),
    ("machine", "y_max"),
    ("machine", "z_max"),
    ("magnet_tool_offset", "x"),
    ("magnet_tool_offset", "y"),
    ("magnet_tool_offset", "z"),
    ("park", "x"),
    ("park", "y"),
    ("park", "safe_z_lift_mm"),
    ("travel", "feed"),
    ("temps", "standby_nozzle_c"),
    ("temps", "nozzle_min_c"),
    ("temps", "nozzle_max_c"),
    ("temps", "bed_min_c"),
    ("temps", "bed_max_c"),
    ("retract", "mm"),
    ("retract", "feed"),
    ("prime", "mm"),
    ("prime", "feed"),
    ("press", "feed"),
    ("press", "dwell_ms"),
    ("shear", "distance"),
    ("shear", "feed"),
    ("gcode", "sentinel_token"),
)


def _deep_merge(base: dict, over: dict) -> dict:
    """Return a new dict: `over` merged onto `base`, recursing into nested dicts."""
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


#: keys whose value must be a number (int/float, not bool)
_NUMERIC_KEYS: tuple[tuple[str, str], ...] = (
    ("printer", "baud"), ("printer", "ack_timeout_s"),
    ("dispenser", "baud"),
    ("machine", "x_max"), ("machine", "y_max"), ("machine", "z_max"),
    ("magnet_tool_offset", "x"), ("magnet_tool_offset", "y"), ("magnet_tool_offset", "z"),
    ("park", "x"), ("park", "y"), ("park", "safe_z_lift_mm"),
    ("travel", "feed"),
    ("temps", "nozzle_min_c"), ("temps", "nozzle_max_c"),
    ("temps", "bed_min_c"), ("temps", "bed_max_c"),
    ("retract", "mm"), ("retract", "feed"), ("prime", "mm"), ("prime", "feed"),
    ("press", "feed"), ("press", "dwell_ms"),
    ("shear", "distance"), ("shear", "feed"),
)


def _validate(config: dict) -> None:
    for section, key in _REQUIRED_KEYS:
        if not isinstance(config.get(section), dict) or key not in config[section]:
            raise KeyError(f"config is missing required key: {section}.{key}")

    for section, key in _NUMERIC_KEYS:
        value = config[section][key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"config {section}.{key} must be a number, got {value!r}")

    token = config["gcode"]["sentinel_token"]
    if not isinstance(token, str) or not token.startswith(";"):
        raise ValueError(f"config gcode.sentinel_token must be a ';' comment, got {token!r}")

    standby = config["temps"]["standby_nozzle_c"]
    if standby is not None and (isinstance(standby, bool) or not isinstance(standby, (int, float))):
        raise ValueError(f"config temps.standby_nozzle_c must be a number or null, got {standby!r}")

    nlo, nhi = config["temps"]["nozzle_min_c"], config["temps"]["nozzle_max_c"]
    if nlo >= nhi:
        raise ValueError(
            f"config temps.nozzle_min_c must be < nozzle_max_c, got {nlo!r} >= {nhi!r}"
        )
    blo, bhi = config["temps"]["bed_min_c"], config["temps"]["bed_max_c"]
    if blo >= bhi:
        raise ValueError(
            f"config temps.bed_min_c must be < bed_max_c, got {blo!r} >= {bhi!r}"
        )

    poll = config.get("ui", {}).get("idle_poll_s", 0)
    if isinstance(poll, bool) or not isinstance(poll, (int, float)) or poll < 0:
        raise ValueError(f"config ui.idle_poll_s must be a number >= 0, got {poll!r}")


def local_config_path(path: str | Path | None = None) -> Path:
    """Where `config.local.yaml` lives for a given base `config.yaml` path."""
    base_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    return base_path.with_name("config.local.yaml")


def save_local_override(updates: dict, path: str | Path | None = None) -> dict:
    """Deep-merge `updates` onto the existing `config.local.yaml` (creating it
    if absent) and write it back. Never touches the committed `config.yaml` -
    see Key Conventions -> Config precedence. Returns the merged local dict."""
    local_path = local_config_path(path)
    if local_path.exists():
        with open(local_path, "r", encoding="utf-8") as fh:
            existing = yaml.safe_load(fh) or {}
    else:
        existing = {}
    merged = _deep_merge(existing, updates)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(merged, fh, sort_keys=False)
    return merged


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load the base config, deep-merge `config.local.yaml` if present, validate.

    `path` overrides the base file location (mainly for tests).
    """
    base_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with open(base_path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    local_path = base_path.with_name("config.local.yaml")
    if local_path.exists():
        with open(local_path, "r", encoding="utf-8") as fh:
            local = yaml.safe_load(fh) or {}
        config = _deep_merge(config, local)

    _validate(config)
    return config
