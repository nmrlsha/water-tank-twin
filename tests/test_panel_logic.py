import twin_logic as t
from twin_state import TwinState


def test_trend_directions():
    assert t.trend([50] * 3)[0] == "unknown"
    assert t.trend([50.0] * 30)[0] == "steady"
    d, rate = t.trend([50 + 0.5 * i for i in range(30)])
    assert d == "rising" and abs(rate - 30.0) < 1e-6
    assert t.trend([80 - 0.2 * i for i in range(30)])[0] == "falling"


def test_trend_labels():
    assert t.trend_label("unknown", 0) == "collecting data..."
    assert t.trend_label("rising", 12.34) == "rising (+12.3 %/min)"


def test_forecast_change_text():
    assert t.forecast_change_text({"level_pct": 40, "predicted_level_pct": 52.3}) == "+12.3 % in 60 s"
    assert t.forecast_change_text({"level_pct": 40, "predicted_level_pct": None}) == "-"
    assert t.forecast_change_text(None) == "-"
    assert t.forecast_change_text({"level_pct": "x", "predicted_level_pct": 1}) == "-"


def test_banner_priority():
    ok = {"alarm": "none", "ai_warning": "none"}
    assert t.banner(ok, "LIVE") == ("NORMAL", t.GREEN)
    assert t.banner({**ok, "ai_warning": "overflow_expected"}, "LIVE") == ("AI WARNING: overflow expected", t.AMBER)
    assert t.banner({**ok, "alarm": "low_level"}, "LIVE") == ("ALARM: low level", t.RED)
    assert t.banner({**ok, "ai_warning": "unavailable"}, "LIVE")[0].startswith("NORMAL (AI")


def test_banner_not_live_never_looks_healthy():
    ok = {"alarm": "none", "ai_warning": "none"}
    text, colour = t.banner(ok, "STALE")
    assert text.startswith("STALE") and "last known" in text and colour == t.AMBER
    assert t.banner(ok, "DISCONNECTED")[1] == t.RED
    assert t.banner(None, "DISCONNECTED") == ("DISCONNECTED", t.RED)


def test_state_keeps_level_history():
    import json
    s = TwinState()
    for i in range(3):
        msg = {"timestamp": "2026-11-02T08:00:00Z", "level_pct": 10 + i, "inflow_lpm": 1,
               "outflow_lpm": 1, "pump_on": False}
        s.apply([("enriched", json.dumps(msg).encode(), 0)])
    assert list(s.levels) == [10.0, 11.0, 12.0]