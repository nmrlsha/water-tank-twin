from storage import Storage

GOOD = {
    "asset_id": "tank_01",
    "timestamp": "2026-11-02T08:00:00Z",
    "level_pct": 62.0,
    "inflow_lpm": 4.2,
    "outflow_lpm": 2.0,
    "pump_on": True,
}


def test_new_database_is_empty(tmp_path):
    db = Storage(str(tmp_path / "test.db"))
    assert db.count() == 0
    db.close()


def test_inserted_row_can_be_read_back(tmp_path):
    db = Storage(str(tmp_path / "test.db"))
    db.insert_state(GOOD)
    row = db.latest(1)[0]
    assert row["level_pct"] == 62.0
    assert row["pump_on"] == 1
    assert row["received_at"] is not None
    db.close()


def test_data_survives_restart(tmp_path):
    path = str(tmp_path / "test.db")
    db = Storage(path)
    db.insert_state(GOOD)
    db.close()                      # simulate stopping the processor
    db2 = Storage(path)             # simulate starting it again
    assert db2.count() == 1
    db2.close()


def test_latest_returns_newest_first(tmp_path):
    db = Storage(str(tmp_path / "test.db"))
    db.insert_state({**GOOD, "level_pct": 10.0})
    db.insert_state({**GOOD, "level_pct": 20.0})
    assert db.latest(2)[0]["level_pct"] == 20.0
    db.close()