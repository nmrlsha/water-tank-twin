"""Runs against the real model file. Skipped where usd-core is not installed."""
from pathlib import Path

import pytest

pytest.importorskip("pxr")
from pxr import Usd, UsdGeom, UsdShade  # noqa: E402

import twin_logic as logic  # noqa: E402
from scene_apply import SceneApplier  # noqa: E402

MODEL = Path(__file__).resolve().parents[1] / "usd" / "tank_twin.usda"
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="usd/tank_twin.usda not found")

DATA = {"level_pct": 60.0, "pump_on": True, "predicted_level_pct": 75.0,
        "alarm": "none", "ai_warning": "none"}


def bound(stage, path):
    return UsdShade.MaterialBindingAPI(stage.GetPrimAtPath(path)).ComputeBoundMaterial()[0].GetPath().pathString


@pytest.fixture
def stage():
    return Usd.Stage.Open(str(MODEL))


def test_model_has_all_prims(stage):
    assert SceneApplier(stage).ready


def test_water_pump_marker_light_follow_data(stage):
    a = SceneApplier(stage)
    a.apply(DATA, "LIVE")
    assert tuple(stage.GetPrimAtPath(logic.PRIM_WATER).GetAttribute("xformOp:scale").Get()) == (1.0, 1.0, 0.6)
    assert bound(stage, logic.PRIM_PUMP) == logic.MAT_PUMP_ON
    assert bound(stage, logic.PRIM_ALARM_LIGHT).endswith("LightGreen")
    z = stage.GetPrimAtPath(logic.PRIM_PREDICTION_MARKER).GetAttribute("xformOp:translate").Get()[2]
    assert abs(z - 0.6) < 1e-9


def test_alarm_and_pump_off(stage):
    a = SceneApplier(stage)
    a.apply({**DATA, "pump_on": False, "alarm": "overflow_risk"}, "LIVE")
    assert bound(stage, logic.PRIM_PUMP) == logic.MAT_PUMP_OFF
    assert bound(stage, logic.PRIM_ALARM_LIGHT).endswith("LightRed")


def test_not_live_turns_light_grey_and_keeps_water(stage):
    a = SceneApplier(stage)
    a.apply(DATA, "LIVE")
    a.apply(DATA, "STALE")
    assert bound(stage, logic.PRIM_ALARM_LIGHT) == logic.MAT_PUMP_OFF
    assert stage.GetPrimAtPath(logic.PRIM_WATER).GetAttribute("xformOp:scale").Get()[2] == 0.6


def test_no_forecast_hides_marker(stage):
    a = SceneApplier(stage)
    a.apply({**DATA, "predicted_level_pct": None}, "LIVE")
    img = UsdGeom.Imageable(stage.GetPrimAtPath(logic.PRIM_PREDICTION_MARKER))
    assert img.ComputeVisibility() == UsdGeom.Tokens.invisible


def test_live_data_never_edits_the_saved_file(stage):
    SceneApplier(stage).apply(DATA, "LIVE")
    assert not stage.GetRootLayer().dirty


def test_wrong_scene_is_reported_not_crashed():
    empty = Usd.Stage.CreateInMemory()
    a = SceneApplier(empty)
    assert not a.ready
    a.apply(DATA, "LIVE")             # must do nothing and not raise