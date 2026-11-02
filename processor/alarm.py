"""Rule-based alarm. This is the BASELINE the AI model will be compared against."""

OVERFLOW_PCT = 90.0           # level at or above this -> overflow risk
LOW_PCT = 10.0                # level at or below this -> low level
ABNORMAL_INFLOW_LPM = 30.0    # inflow at or above this -> abnormal inflow


def rule_based_alarm(data):
    """Return 'overflow_risk', 'low_level', 'abnormal_inflow' or 'none'."""
    if data["level_pct"] >= OVERFLOW_PCT:
        return "overflow_risk"
    if data["level_pct"] <= LOW_PCT:
        return "low_level"
    if data["inflow_lpm"] >= ABNORMAL_INFLOW_LPM:
        return "abnormal_inflow"
    return "none"

def ai_warning(predicted_level_pct):
    """Warning derived from the AI forecast (compare with rule_based_alarm, the baseline)."""
    if predicted_level_pct is None:
        return "unavailable"
    if predicted_level_pct >= OVERFLOW_PCT:
        return "overflow_expected"
    if predicted_level_pct <= LOW_PCT:
        return "low_level_expected"
    return "none"