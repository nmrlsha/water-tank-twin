"""Read-only access to the tank history database (used by the REST API).

Pure sqlite3, so it can be unit tested without FastAPI.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MAX_POINTS = 5000
COLUMNS = ("id, asset_id, timestamp, received_at, level_pct, inflow_lpm, "
           "outflow_lpm, pump_on, predicted_level_pct, alarm")


class DatabaseUnavailable(Exception):
    """The database file does not exist yet (the processor has not created it)."""


def since_iso(minutes, now=None):
    """UTC timestamp string 'minutes' ago. ISO strings sort correctly as text."""
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(minutes=minutes)).strftime(TS_FORMAT)


def _row(r):
    d = dict(r)
    if "pump_on" in d and d["pump_on"] is not None:
        d["pump_on"] = bool(d["pump_on"])
    return d


class HistoryReader:
    def __init__(self, path):
        self.path = str(path)

    def _connect(self):
        if not Path(self.path).exists():
            raise DatabaseUnavailable(self.path)
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")      # this service can never modify the data
        return conn

    def _query(self, sql, params=()):
        conn = self._connect()
        try:
            return conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as error:
            if "no such table" in str(error):        # processor has not written anything yet
                return []
            raise
        finally:
            conn.close()

    def count(self, asset_id):
        rows = self._query("SELECT COUNT(*) AS n FROM tank_state WHERE asset_id = ?", (asset_id,))
        return rows[0]["n"] if rows else 0

    def latest(self, asset_id):
        rows = self._query(f"SELECT {COLUMNS} FROM tank_state WHERE asset_id = ? "
                           "ORDER BY id DESC LIMIT 1", (asset_id,))
        return _row(rows[0]) if rows else None

    def history(self, asset_id, minutes=10, step=1, limit=2000, now=None):
        """Readings from the last 'minutes', oldest first. step=N keeps every Nth row."""
        step = max(1, int(step))
        limit = max(1, min(int(limit), MAX_POINTS))
        rows = self._query(
            f"SELECT {COLUMNS} FROM tank_state "
            "WHERE asset_id = ? AND timestamp >= ? AND id % ? = 0 "
            "ORDER BY id DESC LIMIT ?",
            (asset_id, since_iso(minutes, now), step, limit))
        return [_row(r) for r in reversed(rows)]

    def per_minute(self, asset_id, minutes=10, now=None):
        rows = self._query(
            """SELECT substr(timestamp, 1, 16)            AS minute,
                      ROUND(AVG(level_pct), 2)            AS mean_level_pct,
                      ROUND(MAX(inflow_lpm), 2)           AS max_inflow_lpm,
                      SUM(CASE WHEN alarm IS NOT NULL AND alarm != 'none'
                               THEN 1 ELSE 0 END)         AS alarm_count,
                      COUNT(*)                            AS samples
               FROM tank_state
               WHERE asset_id = ? AND timestamp >= ?
               GROUP BY minute ORDER BY minute""",
            (asset_id, since_iso(minutes, now)))
        return [dict(r) for r in rows]

    def alarm_counts(self, asset_id, minutes=60, now=None):
        rows = self._query(
            "SELECT COALESCE(alarm, 'none') AS alarm, COUNT(*) AS n FROM tank_state "
            "WHERE asset_id = ? AND timestamp >= ? GROUP BY alarm ORDER BY n DESC",
            (asset_id, since_iso(minutes, now)))
        return {r["alarm"]: r["n"] for r in rows}