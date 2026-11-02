"""Live rolling statistics over the most recent readings."""
from collections import deque


class RollingStats:
    def __init__(self, window=60):
        self.levels = deque(maxlen=window)    # maxlen drops the oldest item automatically
        self.inflows = deque(maxlen=window)

    def update(self, level_pct, inflow_lpm):
        self.levels.append(level_pct)
        self.inflows.append(inflow_lpm)
        return {
            "rolling_mean_level_pct": round(sum(self.levels) / len(self.levels), 2),
            "rolling_max_inflow_lpm": round(max(self.inflows), 2),
        }