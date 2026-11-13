"""Reads stored history from the REST API (port 8000). No Kit imports, standard library only.

The network call runs on a BACKGROUND thread (same rule as MQTT: never wait for the network
on Kit's update tick). The Kit side calls request(), then poll() on later ticks.
"""
import json
import queue
import threading
import time
import urllib.error
import urllib.request

MAX_POINTS = 300                      # enough for a readable plot; /history thins the rest with `step`
LIST_KEYS = ("rows", "data", "history", "items", "readings", "results", "aggregates")


def extract_rows(payload):
    """The API may answer with a list, or a dict that holds the list. Returns a list of dicts."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in LIST_KEYS:
            if isinstance(payload.get(key), list):
                return [r for r in payload[key] if isinstance(r, dict)]
    return []


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None          # NaN -> None


def summarize(rows):
    """Plot values and short facts from /history rows (oldest first)."""
    levels = [v for v in (_number(r.get("level_pct")) for r in rows) if v is not None]
    alarms = sum(1 for r in rows if r.get("alarm") not in (None, "none"))
    stamps = [r.get("timestamp") for r in rows if r.get("timestamp")]
    return {
        "levels": levels,
        "alarm_readings": alarms,
        "first_timestamp": stamps[0] if stamps else None,
        "last_timestamp": stamps[-1] if stamps else None,
    }


def aggregate_lines(rows, count=3):
    """Last few /aggregates rows as plain text, whatever the field names are."""
    lines = []
    for row in rows[-count:]:
        parts = []
        for key, value in row.items():
            parts.append(f"{key}={round(value, 1) if isinstance(value, float) else value}")
        lines.append(", ".join(parts))
    return lines


def points_step(minutes, max_points=MAX_POINTS):
    """Keep every n-th reading (readings arrive at 1 per second) so the plot has <= max_points."""
    return max(1, int(minutes * 60 / max_points))


class HistoryClient:
    def __init__(self, base_url="http://127.0.0.1:8000", timeout_s=3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._results = queue.Queue()
        self._lock = threading.Lock()
        self._busy = False

    # ---- blocking part (runs on the worker thread, or directly in tests) -------------
    def _get_json(self, path):
        with urllib.request.urlopen(self.base_url + path, timeout=self.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch(self, minutes):
        """Returns a result dict. Never raises: problems come back as result['error']."""
        result = {"ok": False, "minutes": minutes, "error": None, "fetched_at": time.time(),
                  "levels": [], "alarm_readings": 0, "first_timestamp": None,
                  "last_timestamp": None, "aggregate_lines": []}
        try:
            step = points_step(minutes)
            history = self._get_json(f"/history?minutes={minutes}&step={step}&limit=2000")
            rows = extract_rows(history)
            if not rows:
                result["error"] = "no stored readings in this period"
                return result
            result.update(summarize(rows))
            try:                                          # aggregates are a bonus: never fail on them
                result["aggregate_lines"] = aggregate_lines(extract_rows(
                    self._get_json(f"/aggregates?minutes={minutes}")))
            except Exception:
                result["aggregate_lines"] = ["aggregates unavailable"]
            result["ok"] = len(result["levels"]) > 0
            if not result["ok"]:
                result["error"] = "stored rows have no level values"
        except urllib.error.HTTPError as error:
            hint = {503: "database not created yet", 404: "no data stored yet"}.get(error.code, "")
            result["error"] = f"history unavailable (HTTP {error.code}{': ' + hint if hint else ''})"
        except urllib.error.URLError as error:
            result["error"] = f"history unavailable (API not reachable: {error.reason})"
        except Exception as error:                       # timeout, bad JSON, anything else
            result["error"] = f"history unavailable ({type(error).__name__})"
        return result

    # ---- non-blocking part (called from Kit's update tick) ---------------------------
    @property
    def busy(self):
        return self._busy

    def request(self, minutes):
        """Start a fetch in the background. Ignored (returns False) if one is already running."""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
        threading.Thread(target=self._worker, args=(minutes,), daemon=True).start()
        return True

    def _worker(self, minutes):
        try:
            self._results.put(self.fetch(minutes))
        finally:
            self._busy = False

    def poll(self):
        """Newest finished result, or None. Never blocks."""
        latest = None
        while True:
            try:
                latest = self._results.get_nowait()
            except queue.Empty:
                return latest