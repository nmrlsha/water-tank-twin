"""Runs panel.py against a FAKE omni.ui, only to catch typos and logic slips outside Kit.
It does NOT prove the panel looks right in Kit."""
import json
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def panel_module(monkeypatch):
    fake_ui = MagicMock()
    fake_ui.Label.side_effect = lambda *a, **k: MagicMock(text=a[0] if a else "")
    omni = MagicMock()
    omni.ui = fake_ui
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.ui", fake_ui)
    monkeypatch.setitem(sys.modules, "omni.ui.color", fake_ui.color)
    sys.modules.pop("panel", None)
    import panel
    yield panel
    sys.modules.pop("panel", None)


def make_state(level=60, forecast=75, status="live"):
    from twin_state import TwinState
    s = TwinState(clock=lambda: 100.0)
    msg = {"timestamp": "2026-11-02T08:00:00Z", "level_pct": level, "inflow_lpm": 4.2, "outflow_lpm": 2.0,
           "pump_on": True, "predicted_level_pct": forecast, "horizon_s": 60,
           "alarm": "none", "ai_warning": "overflow_expected"}
    stat = {"processor": "online", "source": status}
    s.apply([("enriched", json.dumps(msg).encode(), 100.2), ("status", json.dumps(stat).encode(), 100.0)])
    return s


def test_update_fills_labels_and_banner(panel_module):
    p = panel_module.TankPanel()
    p.update(make_state())
    assert p._values["Water level"].text == "60.0 %"
    assert p._values["Forecast change"].text == "+15.0 % in 60 s"
    assert p._banner[0] == "AI WARNING: overflow expected"


def test_update_with_no_data_does_not_crash(panel_module):
    from twin_state import TwinState
    p = panel_module.TankPanel()
    p.update(TwinState())
    assert p._values["Water level"].text == "-"
    assert p._banner[0] == "DISCONNECTED"


def test_stale_banner(panel_module):
    p = panel_module.TankPanel()
    p.update(make_state(status="stale"))
    assert p._banner[0].startswith("STALE")