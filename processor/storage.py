"""SQLite storage for tank states. Matches the table in docs/schema.md."""
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tank_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,           -- when the sensor took the reading (UTC)
    received_at TEXT NOT NULL,         -- when the processor received it (UTC)
    level_pct REAL,
    inflow_lpm REAL,
    outflow_lpm REAL,
    pump_on INTEGER,
    predicted_level_pct REAL,          -- filled in later by the AI step
    alarm TEXT                         -- filled in later
);
CREATE INDEX IF NOT EXISTS idx_time ON tank_state(asset_id, timestamp);
"""


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class Storage:
    def __init__(self, path="data/tank.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)   # create data/ if missing
        # The MQTT library calls us from a background thread, so allow that and use a lock.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL;")      # lets Grafana read while we write
            self.conn.executescript(SCHEMA)

    def insert_state(self, data, predicted_level_pct=None, alarm=None):
        """Save one validated message."""
        with self.lock:
            self.conn.execute(
                """INSERT INTO tank_state
                   (asset_id, timestamp, received_at, level_pct, inflow_lpm,
                    outflow_lpm, pump_on, predicted_level_pct, alarm)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["asset_id"], data["timestamp"], utc_now_iso(),
                 data["level_pct"], data["inflow_lpm"], data["outflow_lpm"],
                 1 if data["pump_on"] else 0, predicted_level_pct, alarm),
            )
            self.conn.commit()     # commit = make it permanent on disk

    def count(self):
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM tank_state").fetchone()[0]

    def latest(self, n=10):
        """Most recent n rows, newest first."""
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM tank_state ORDER BY id DESC LIMIT ?", (n,)).fetchall()
        return [dict(r) for r in rows]


    def per_minute(self, minutes=10):
        """Summary of each recent minute: mean level, max inflow, alarm count, sample count."""
        with self.lock:
            rows = self.conn.execute(
                """SELECT substr(timestamp, 1, 16)            AS minute,
                          ROUND(AVG(level_pct), 2)            AS mean_level_pct,
                          ROUND(MAX(inflow_lpm), 2)           AS max_inflow_lpm,
                          SUM(CASE WHEN alarm IS NOT NULL AND alarm != 'none'
                                   THEN 1 ELSE 0 END)         AS alarm_count,
                          COUNT(*)                            AS samples
                   FROM tank_state
                   GROUP BY minute
                   ORDER BY minute DESC
                   LIMIT ?""", (minutes,)).fetchall()
        return [dict(r) for r in rows]
    
    def close(self):
        with self.lock:
            self.conn.close()