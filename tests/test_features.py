from features import FEATURE_NAMES, WINDOW, build_features


def reading(level, inflow=10.0, outflow=0.0, pump=False):
    return {"level_pct": level, "inflow_lpm": inflow, "outflow_lpm": outflow, "pump_on": pump}


def test_too_little_history_returns_none():
    assert build_features([reading(50.0)] * (WINDOW - 1)) is None


def test_feature_values_for_a_steadily_rising_level():
    window = [reading(float(i)) for i in range(WINDOW)]       # levels 0, 1, ... 30
    f = dict(zip(FEATURE_NAMES, build_features(window)))
    assert f["level_now"] == 30.0
    assert f["level_change_10s"] == 10.0
    assert f["level_change_30s"] == 30.0
    assert f["mean_inflow_10s"] == 10.0
    assert f["pump_on_fraction_30s"] == 0.0


def test_net_flow_is_inflow_minus_outflow():
    window = [reading(50.0, inflow=8.0, outflow=20.0, pump=True)] * WINDOW
    f = dict(zip(FEATURE_NAMES, build_features(window)))
    assert f["net_flow_now"] == -12.0
    assert f["mean_net_flow_10s"] == -12.0
    assert f["mean_net_flow_30s"] == -12.0


def test_only_the_latest_window_is_used():
    old = [reading(99.0)] * 20
    recent = [reading(float(i)) for i in range(WINDOW)]
    assert build_features(old + recent) == build_features(recent)


def test_feature_count_matches_names():
    assert len(build_features([reading(50.0)] * WINDOW)) == len(FEATURE_NAMES)