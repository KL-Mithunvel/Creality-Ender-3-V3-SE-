"""`magnet_embed.ui.settings_dialog` - pure helper (Settings dialog)."""

from __future__ import annotations

import pytest

from magnet_embed.ui.settings_dialog import build_updates


def test_build_updates_parses_fields():
    u = build_updates(
        printer_port=" COM5 ", dispenser_port="COM6",
        offset_x="31.5", offset_y="0", offset_z="2.0",
    )
    assert u == {
        "printer": {"port": "COM5"},
        "dispenser": {"port": "COM6"},
        "magnet_tool_offset": {"x": 31.5, "y": 0.0, "z": 2.0},
    }


def test_build_updates_rejects_bad_offset():
    with pytest.raises(ValueError):
        build_updates(
            printer_port="COM5", dispenser_port="COM6",
            offset_x="abc", offset_y="0", offset_z="0",
        )
