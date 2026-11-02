from alarm import rule_based_alarm

NORMAL = {"level_pct": 50.0, "inflow_lpm": 8.0}


def test_normal_state_has_no_alarm():
    assert rule_based_alarm(NORMAL) == "none"


def test_high_level_is_overflow_risk():
    assert rule_based_alarm({**NORMAL, "level_pct": 92.0}) == "overflow_risk"


def test_low_level_is_flagged():
    assert rule_based_alarm({**NORMAL, "level_pct": 5.0}) == "low_level"


def test_high_inflow_is_abnormal_inflow():
    assert rule_based_alarm({**NORMAL, "inflow_lpm": 40.0}) == "abnormal_inflow"


def test_overflow_takes_priority_over_inflow():
    assert rule_based_alarm({"level_pct": 95.0, "inflow_lpm": 40.0}) == "overflow_risk"