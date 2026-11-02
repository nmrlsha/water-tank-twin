from features import WINDOW
from predictor import Predictor


class FakeModel:
    """Always predicts the same change in level."""
    def __init__(self, change):
        self.change = change

    def predict(self, rows):
        return [self.change] * len(rows)


def message(i, level=50.0):
    return {"timestamp": f"2026-11-02T08:{i // 60:02d}:{i % 60:02d}Z", "level_pct": level,
            "inflow_lpm": 10.0, "outflow_lpm": 0.0, "pump_on": False}


def feed(predictor, count, level=50.0):
    result = None
    for i in range(count):
        result = predictor.update(message(i, level))
    return result


def test_no_prediction_until_window_is_full():
    assert feed(Predictor(FakeModel(5.0)), WINDOW - 1) is None


def test_prediction_is_level_plus_predicted_change():
    assert feed(Predictor(FakeModel(5.0)), WINDOW, level=50.0) == 55.0


def test_prediction_is_clipped_at_100():
    assert feed(Predictor(FakeModel(30.0)), WINDOW, level=90.0) == 100.0


def test_prediction_is_clipped_at_0():
    assert feed(Predictor(FakeModel(-30.0)), WINDOW, level=10.0) == 0.0


def test_gap_in_stream_resets_history():
    p = Predictor(FakeModel(5.0))
    assert feed(p, WINDOW) is not None
    assert p.update(message(WINDOW + 100)) is None       # 100 s of silence, so history restarts