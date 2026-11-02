"""Loads the trained model and predicts the water level HORIZON seconds ahead."""
from collections import deque
from datetime import datetime

import joblib

from features import WINDOW, build_features

MAX_GAP_S = 5                              # a longer silence means the history is no longer continuous
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class Predictor:
    def __init__(self, model, horizon_s=60):
        self.model = model
        self.horizon_s = horizon_s
        self.window = deque(maxlen=WINDOW)
        self._last_ts = None
        if hasattr(model, "n_jobs"):
            model.n_jobs = 1               # one prediction per second does not need parallel threads

    @classmethod
    def from_file(cls, path):
        bundle = joblib.load(path)
        if bundle.get("target") != "delta_level_pct":
            raise ValueError("Model file was not trained with the delta-level target")
        return cls(bundle["model"], bundle["horizon_s"])

    def update(self, data):
        """Feed one validated reading. Returns the predicted level (%) at +horizon,
        or None while there is not enough continuous history yet."""
        ts = datetime.strptime(data["timestamp"], TS_FORMAT)
        if self._last_ts is not None:
            gap = (ts - self._last_ts).total_seconds()
            if gap > MAX_GAP_S or gap < 0:
                self.window.clear()        # stream was interrupted: restart the history
        self._last_ts = ts

        self.window.append({
            "level_pct": data["level_pct"],
            "inflow_lpm": data["inflow_lpm"],
            "outflow_lpm": data["outflow_lpm"],
            "pump_on": data["pump_on"],
        })
        features = build_features(list(self.window))
        if features is None:
            return None
        change = float(self.model.predict([features])[0])
        return round(min(100.0, max(0.0, data["level_pct"] + change)), 2)   # keep inside 0..100