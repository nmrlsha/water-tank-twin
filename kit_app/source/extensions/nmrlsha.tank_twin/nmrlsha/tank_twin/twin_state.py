"""Collects what the listener received and answers: what do we show right now?

Still no Kit imports. Uses the decisions in twin_logic.py.
"""
import time
from collections import deque
from datetime import datetime, timezone

try:                                  # inside Kit this file is part of a package
    from . import twin_logic as logic
except ImportError:                   # on the laptop / pytest it is a plain module
    import twin_logic as logic


def timestamp_to_epoch(text):
    """'2026-11-02T08:00:00Z' -> seconds since 1970 (UTC), or None if malformed."""
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return None


class TwinState:
    def __init__(self, timeout_s=5.0, clock=time.time):
        self.timeout_s = timeout_s
        self._clock = clock
        self.data = None                 # latest valid enriched message
        self.status = None               # latest status message
        self.status_received_at = None
        self.rejected = 0                # unusable messages seen by the extension
        self.delays = deque(maxlen=600)  # data-to-display delays in seconds
        self.levels = deque(maxlen=120)  # last 2 minutes of water level, for the trend plot

    def apply(self, items):
        """Feed in the list from TankListener.drain(). Returns True if the data changed."""
        changed = False
        for kind, payload, received_at in items:
            message = logic.parse_message(payload)
            if kind == "status":
                if message is None:
                    self.rejected += 1
                    continue
                self.status, self.status_received_at = message, received_at
            elif logic.is_valid_enriched(message):
                self.data = message
                changed = True
                try:
                    self.levels.append(float(message["level_pct"]))
                except (TypeError, ValueError):
                    pass
                sent_at = timestamp_to_epoch(message["timestamp"])
                if sent_at is not None:
                    self.delays.append(received_at - sent_at)
            else:
                self.rejected += 1
        return changed

    def trend(self):
        return logic.trend(self.levels)

    def connection(self):
        age = None if self.status_received_at is None else self._clock() - self.status_received_at
        return logic.connection_state(self.status, age, self.timeout_s)

    def rows(self):
        return logic.panel_rows(self.data, self.connection())

    def delay_summary(self):
        """(latest, mean, max) in seconds, or None before any data. Includes up to 1 s of
        timestamp rounding, because message timestamps have whole-second resolution."""
        if not self.delays:
            return None
        return self.delays[-1], sum(self.delays) / len(self.delays), max(self.delays)