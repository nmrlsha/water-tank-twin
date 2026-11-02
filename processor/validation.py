"""Checks one raw tank message against the schema in docs/schema.md.

No networking here, so it can be unit tested on its own.
"""
import json
import math
from datetime import datetime

EXPECTED_ASSET = "tank_01"
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"      # UTC, e.g. 2026-11-02T08:00:00Z
REQUIRED_FIELDS = ("asset_id", "timestamp", "level_pct", "inflow_lpm", "outflow_lpm", "pump_on")
NUMERIC_RANGES = {
    "level_pct": (0.0, 100.0),
    "inflow_lpm": (0.0, 50.0),
    "outflow_lpm": (0.0, 50.0),
}


def validate_message(raw):
    """Return (data, None) if the message is valid, or (None, reason) if rejected."""
    # 1. Is it readable JSON?
    try:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "not valid JSON"
    if not isinstance(data, dict):
        return None, "JSON is not an object"

    # 2. Are all fields present?
    for field in REQUIRED_FIELDS:
        if field not in data:
            return None, f"missing field: {field}"

    # 3. Right asset and a proper UTC timestamp?
    if data["asset_id"] != EXPECTED_ASSET:
        return None, f"unexpected asset_id: {data['asset_id']!r}"
    try:
        datetime.strptime(data["timestamp"], TIMESTAMP_FORMAT)
    except (ValueError, TypeError):
        return None, "timestamp is not UTC ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)"

    # 4. Numbers within their valid ranges?
    for name, (low, high) in NUMERIC_RANGES.items():
        value = data[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, f"{name} is not a number"
        if math.isnan(value) or not (low <= value <= high):
            return None, f"{name} out of range ({low} to {high}): {value}"

    # 5. Pump state must be true/false
    if not isinstance(data["pump_on"], bool):
        return None, "pump_on is not true/false"

    return data, None