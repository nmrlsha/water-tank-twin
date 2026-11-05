import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from reader import DatabaseUnavailable, HistoryReader
from storage import Storage

NOW = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)


def stamp(seconds_ago):
    return (NOW - timedelta(seconds=seconds_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def reading(seconds_ago, level=50.0, inflow=8.0):
    return {"asset_id": "tank_01", "timestamp": stamp(seconds_ago), "level_pct": level,
            "inflow_lpm": inflow, "outflow_lpm": 0.0, "pump_on": False}


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "t.db")


def fill(db_path, rows):
    db = Storage(db_path)
    for data, alarm in rows:
        db.insert_state(data, predicted_level_pct=data["level_pct"] + 1, alarm=alarm)
    db.close()


def test_missing_database_raises(tmp_path):
    with pytest.raises(DatabaseUnavailable):
        HistoryReader(str(tmp_path / "nope.db")).latest("tank_01")


def test_empty_database_returns_none_and_zero(db_path):
    Storage(db_path).close()
    r = HistoryReader(db_path)
    assert r.latest("tank_01") is None
    assert r.count("tank_01") == 0


def test_database_without_table_is_treated_as_empty(db_path):
    sqlite3.connect(db_path).close()
    assert HistoryReader(db_path).latest("tank_01") is None


def test_latest_returns_newest_row_with_boolean_pump(db_path):
    fill(db_path, [(reading(20, level=10.0), "none"), (reading(10, level=20.0), "none")])
    row = HistoryReader(db_path).latest("tank_01")
    assert row["level_pct"] == 20.0
    assert row["pump_on"] is False
    assert row["predicted_level_pct"] == 21.0


def test_history_is_oldest_first_and_respects_the_time_window(db_path):
    fill(db_path, [(reading(7200, level=1.0), "none"),        # 2 hours old: outside a 10-minute window
                   (reading(120, level=2.0), "none"),
                   (reading(60, level=3.0), "none")])
    points = HistoryReader(db_path).history("tank_01", minutes=10, now=NOW)
    assert [p["level_pct"] for p in points] == [2.0, 3.0]


def test_history_step_thins_the_data(db_path):
    fill(db_path, [(reading(100 - i), "none") for i in range(10)])
    r = HistoryReader(db_path)
    assert len(r.history("tank_01", minutes=10, step=1, now=NOW)) == 10
    assert len(r.history("tank_01", minutes=10, step=5, now=NOW)) == 2


def test_history_limit_keeps_the_most_recent_points(db_path):
    fill(db_path, [(reading(100 - i, level=float(i)), "none") for i in range(10)])
    points = HistoryReader(db_path).history("tank_01", minutes=10, limit=3, now=NOW)
    assert [p["level_pct"] for p in points] == [7.0, 8.0, 9.0]


def test_per_minute_summary(db_path):
    fill(db_path, [(reading(90, level=10.0, inflow=5.0), "none"),
                   (reading(80, level=20.0, inflow=9.0), "overflow_risk")])
    rows = HistoryReader(db_path).per_minute("tank_01", minutes=10, now=NOW)
    assert len(rows) == 1
    assert rows[0]["mean_level_pct"] == 15.0
    assert rows[0]["max_inflow_lpm"] == 9.0
    assert rows[0]["alarm_count"] == 1
    assert rows[0]["samples"] == 2


def test_alarm_counts(db_path):
    fill(db_path, [(reading(50), "none"), (reading(40), "overflow_risk"),
                   (reading(30), "overflow_risk")])
    counts = HistoryReader(db_path).alarm_counts("tank_01", minutes=10, now=NOW)
    assert counts == {"overflow_risk": 2, "none": 1}


def test_reader_connection_cannot_write(db_path):
    Storage(db_path).close()
    conn = HistoryReader(db_path)._connect()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM tank_state")
    conn.close()