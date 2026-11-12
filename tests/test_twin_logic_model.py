import twin_logic as t


def test_water_scale_only_changes_z():
    assert t.water_scale_vector(50) == (1.0, 1.0, 0.5)
    assert t.water_scale_vector(0)[2] == t.WATER_MIN_SCALE
    assert t.water_scale_vector(150)[2] == 1.0


def test_pump_material():
    assert t.pump_material(True) == "/World/Looks/Mat_PumpOn"
    assert t.pump_material(False) == "/World/Looks/Mat_PumpOff"


def test_alarm_material_levels():
    assert t.alarm_material({"alarm": "none", "ai_warning": "none"}).endswith("LightGreen")
    assert t.alarm_material({"alarm": "none", "ai_warning": "overflow_expected"}).endswith("LightAmber")
    assert t.alarm_material({"alarm": "overflow_risk", "ai_warning": "none"}).endswith("LightRed")


def test_prediction_marker_height():
    assert abs(t.prediction_marker_z(75) - 0.6) < 1e-9
    assert t.prediction_marker_z(-5) == 0.0 and abs(t.prediction_marker_z(120) - 0.8) < 1e-9


def test_prediction_marker_unusable_values():
    for bad in (None, "x", float("nan")):
        assert t.prediction_marker_z(bad) is None