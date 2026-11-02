import json

from validation import validate_message

GOOD = {
    "asset_id": "tank_01",
    "timestamp": "2026-11-02T08:00:00Z",
    "level_pct": 62.0,
    "inflow_lpm": 4.2,
    "outflow_lpm": 2.0,
    "pump_on": True,
}


def check(**changes):
    return validate_message(json.dumps({**GOOD, **changes}))


def test_valid_message_is_accepted():
    data, reason = check()
    assert reason is None
    assert data["level_pct"] == 62.0


def test_not_json_is_rejected():
    data, reason = validate_message("this is not json")
    assert data is None and "JSON" in reason


def test_missing_field_is_rejected():
    bad = dict(GOOD)
    del bad["inflow_lpm"]
    data, reason = validate_message(json.dumps(bad))
    assert data is None and "inflow_lpm" in reason


def test_level_above_100_is_rejected():
    data, reason = check(level_pct=150.0)
    assert data is None and "level_pct" in reason


def test_negative_flow_is_rejected():
    data, reason = check(inflow_lpm=-5.0)
    assert data is None and "inflow_lpm" in reason


def test_wrong_asset_is_rejected():
    data, reason = check(asset_id="tank_99")
    assert data is None and "asset_id" in reason


def test_bad_timestamp_is_rejected():
    data, reason = check(timestamp="yesterday")
    assert data is None and "timestamp" in reason


def test_boolean_is_not_accepted_as_a_number():
    data, reason = check(level_pct=True)
    assert data is None


def test_pump_state_must_be_boolean():
    data, reason = check(pump_on="yes")
    assert data is None and "pump_on" in reason