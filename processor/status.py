"""Tracks whether the data source is alive, and builds the status message."""
import threading

STALE_AFTER_S = 5.0     # no valid message for this long -> the source is "stale"


class SourceMonitor:
    def __init__(self, stale_after_s=STALE_AFTER_S):
        self.stale_after_s = stale_after_s
        self._lock = threading.Lock()          # MQTT thread writes, main thread reads
        self.valid = 0
        self.rejected = 0
        self._last_valid_mono = None
        self._last_data_ts = None

    def record_valid(self, now_mono, data_timestamp):
        with self._lock:
            self.valid += 1
            self._last_valid_mono = now_mono
            self._last_data_ts = data_timestamp

    def record_rejected(self):
        with self._lock:
            self.rejected += 1                 # garbage does not count as a live source

    def snapshot(self, now_mono):
        with self._lock:
            if self._last_valid_mono is None:
                source, age = "never_seen", None
            else:
                age = now_mono - self._last_valid_mono
                source = "live" if age <= self.stale_after_s else "stale"
            return {
                "source": source,
                "seconds_since_last_data": None if age is None else round(age, 1),
                "last_data_timestamp": self._last_data_ts,
                "messages_valid": self.valid,
                "messages_rejected": self.rejected,
            }


def status_message(asset_id, timestamp, processor_state, snapshot=None):
    """The JSON-ready dict published on twin/<asset>/status."""
    message = {"asset_id": asset_id, "timestamp": timestamp, "processor": processor_state}
    if snapshot is None:
        message["source"] = "unknown"
    else:
        message.update(snapshot)
    return message