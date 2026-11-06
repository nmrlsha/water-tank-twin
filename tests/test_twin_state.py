import json

from twin_state import TwinState, timestamp_to_epoch

GOOD = {"asset_id": "tank_01", "timestamp": "2026-11-02T08:00:00Z", "level_pct": 62.0,
        "inflow_lpm": 4.2, "outflow_lpm": 2.0, "pump_on": True}
T0 = timestamp_to_epoch(GOOD["timestamp"])


def enc(d):
    return json.dumps(d).encode()


def test_timestamp_parsing():
    assert timestamp_to_epoch("1970-01-01T00:00:10Z") == 10
    assert timestamp_to_epoch("garbage") is None and timestamp_to_epoch(None) is None


def test_valid_data_is_stored_and_delay_measured():
    s = TwinState()
    assert s.apply([("enriched", enc(GOOD), T0 + 0.4)]) is True
    assert s.data["level_pct"] == 62.0
    assert abs(s.delay_summary()[0] - 0.4) < 1e-6


def test_bad_data_counted_and_ignored():
    s = TwinState()
    items = [("enriched", b"not json", T0), ("enriched", enc({"level_pct": 1}), T0),
             ("status", b"[]", T0)]
    assert s.apply(items) is False
    assert s.data is None and s.rejected == 3 and s.delay_summary() is None


def test_connection_follows_status_and_silence():
    now = [1000.0]
    s = TwinState(clock=lambda: now[0])
    assert s.connection() == "DISCONNECTED"              # nothing heard yet
    live = {"processor": "online", "source": "live"}
    s.apply([("status", enc(live), 1000.0)])
    assert s.connection() == "LIVE"
    s.apply([("status", enc({"processor": "online", "source": "stale"}), 1000.0)])
    assert s.connection() == "STALE"
    now[0] = 1006.0                                       # 6 s of silence
    assert s.connection() == "DISCONNECTED"


def test_rows_mark_old_values_when_not_live():
    s = TwinState(clock=lambda: 1000.0)
    s.apply([("enriched", enc(GOOD), 1000.0),
             ("status", enc({"processor": "online", "source": "stale"}), 1000.0)])
    assert "(last known)" in dict(s.rows())["Water level"]