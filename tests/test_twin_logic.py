import json

from twin_logic import (AMBER, GREEN, GREY, RED, WATER_MIN_SCALE, alarm_colour, alarm_level,
                        connection_state, is_valid_enriched, panel_rows, parse_message,
                        pump_colour, water_scale_y)

GOOD = {"timestamp": "2026-11-08T09:00:00Z", "level_pct": 62.0, "inflow_lpm": 4.2,
        "outflow_lpm": 2.0, "pump_on": True, "predicted_level_pct": 70.0, "horizon_s": 60,
        "alarm": "none", "ai_warning": "none"}


# ---- parsing ----
def test_parse_valid_json():
    assert parse_message(json.dumps(GOOD).encode())["level_pct"] == 62.0


def test_parse_garbage_returns_none():
    assert parse_message(b"not json") is None
    assert parse_message(b"\xff\xfe") is None
    assert parse_message("[1, 2, 3]") is None
    assert parse_message(None) is None


def test_enriched_validity():
    assert is_valid_enriched(GOOD)
    assert not is_valid_enriched({"level_pct": 50})
    assert not is_valid_enriched(None)


# ---- water ----
def test_water_scale_follows_level():
    assert water_scale_y(50.0) == 0.5
    assert water_scale_y(100.0) == 1.0


def test_water_scale_is_clamped_and_never_zero():
    assert water_scale_y(0.0) == WATER_MIN_SCALE
    assert water_scale_y(-20.0) == WATER_MIN_SCALE
    assert water_scale_y(140.0) == 1.0


# ---- lights ----
def test_pump_colour():
    assert pump_colour(True) == GREEN
    assert pump_colour(False) == GREY


def test_rule_alarm_is_red():
    for name in ("overflow_risk", "low_level", "abnormal_inflow"):
        assert alarm_level({"alarm": name}) == "alarm"
        assert alarm_colour({"alarm": name}) == RED


def test_ai_warning_is_amber():
    assert alarm_level({"alarm": "none", "ai_warning": "overflow_expected"}) == "warning"
    assert alarm_colour({"alarm": "none", "ai_warning": "overflow_expected"}) == AMBER


def test_rule_alarm_beats_ai_warning():
    assert alarm_level({"alarm": "overflow_risk", "ai_warning": "overflow_expected"}) == "alarm"


def test_no_alarm_is_green_and_unavailable_forecast_is_not_a_warning():
    assert alarm_level({"alarm": "none", "ai_warning": "none"}) == "ok"
    assert alarm_level({"alarm": "none", "ai_warning": "unavailable"}) == "ok"
    assert alarm_colour({}) == GREEN


# ---- connection state ----
def status(processor="online", source="live"):
    return {"processor": processor, "source": source}


def test_live():
    assert connection_state(status(), 1.0) == "LIVE"


def test_stale_when_sensor_stops():
    assert connection_state(status(source="stale"), 1.0) == "STALE"


def test_waiting_before_first_data():
    assert connection_state(status(source="never_seen"), 1.0) == "WAITING"


def test_disconnected_when_processor_offline():
    assert connection_state(status(processor="offline", source="unknown"), 1.0) == "DISCONNECTED"


def test_disconnected_when_status_messages_stop_arriving():
    assert connection_state(status(), 6.0) == "DISCONNECTED"        # broker or network died
    assert connection_state(status(), 5.0) == "LIVE"                # exactly at the limit is fine


def test_disconnected_when_nothing_received_yet():
    assert connection_state(None, None) == "DISCONNECTED"


# ---- panel text ----
def rows(data, state):
    return dict(panel_rows(data, state))


def test_panel_live_values_have_no_last_known_note():
    r = rows(GOOD, "LIVE")
    assert r["Water level"] == "62.0 %"
    assert r["Pump"] == "ON"
    assert r["AI forecast"] == "70.0 % in 60 s"


def test_panel_stale_values_are_marked_last_known():
    r = rows(GOOD, "STALE")
    assert "(last known)" in r["Water level"]
    assert "(last known)" in r["Pump"]
    assert r["Connection"] == "STALE"


def test_panel_without_forecast_says_so():
    r = rows({**GOOD, "predicted_level_pct": None}, "LIVE")
    assert r["AI forecast"] == "not available yet"


def test_panel_without_any_data():
    r = rows(None, "DISCONNECTED")
    assert r["Connection"] == "DISCONNECTED"
    assert "Water level" not in r