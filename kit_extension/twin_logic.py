"""The 'brain' of the Kit extension: turns messages into display decisions.

No Kit imports in this file, so it runs and is unit tested on any laptop.
The Kit extension (written later) only has to APPLY what this file decides.
"""
import json

# ---- Where things live in usd/tank.usda (see usd/build_tank.py) -----------------
PRIM_WATER = "/World/Tank/Water"              # scale Y  <- level
PRIM_PUMP_LIGHT = "/World/Pump/Indicator"     # colour   <- pump on/off
PRIM_ALARM_LIGHT = "/World/Tank/AlarmLight"   # colour   <- alarm state

WATER_MIN_SCALE = 0.001                       # a scale of exactly 0 can break 3D maths

# ---- Colours (red, green, blue from 0 to 1) --------------------------------------
GREEN = (0.10, 0.80, 0.20)
AMBER = (1.00, 0.70, 0.00)
RED = (0.90, 0.10, 0.10)
GREY = (0.55, 0.55, 0.55)

ALARMS_RED = ("overflow_risk", "low_level", "abnormal_inflow")      # from the threshold rules
WARNINGS_AMBER = ("overflow_expected", "low_level_expected")        # from the AI forecast
REQUIRED_FIELDS = ("timestamp", "level_pct", "inflow_lpm", "outflow_lpm", "pump_on")

STATE_COLOURS = {"LIVE": GREEN, "STALE": AMBER, "WAITING": GREY, "DISCONNECTED": RED}


def parse_message(payload):
    """Bytes or text from MQTT -> dict, or None if it is unusable. Never raises."""
    try:
        text = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else payload
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def is_valid_enriched(data):
    return isinstance(data, dict) and all(f in data for f in REQUIRED_FIELDS)


def water_scale_y(level_pct):
    """Level in % -> the Y scale of the water prim (0.0 to 1.0, never exactly 0)."""
    level = max(0.0, min(100.0, float(level_pct)))
    return max(level / 100.0, WATER_MIN_SCALE)


def pump_colour(pump_on):
    return GREEN if pump_on else GREY


def alarm_level(data):
    """'alarm' (red), 'warning' (amber) or 'ok' (green)."""
    if data.get("alarm") in ALARMS_RED:
        return "alarm"
    if data.get("ai_warning") in WARNINGS_AMBER:
        return "warning"
    return "ok"


def alarm_colour(data):
    return {"alarm": RED, "warning": AMBER, "ok": GREEN}[alarm_level(data)]


def connection_state(status, status_age_s, timeout_s=5.0):
    """What the display should say about the data feed.

    status       the latest message from twin/tank_01/status (dict), or None if none yet
    status_age_s seconds since we last RECEIVED any status message (None if never)
    Returns 'LIVE', 'STALE', 'WAITING' or 'DISCONNECTED'.
    """
    if status is None or status_age_s is None or status_age_s > timeout_s:
        return "DISCONNECTED"                     # we hear nothing: broker or network is down
    if status.get("processor") == "offline":
        return "DISCONNECTED"                     # the processor is down
    source = status.get("source")
    if source == "live":
        return "LIVE"
    if source == "stale":
        return "STALE"                            # processor is fine, the sensor stopped
    if source == "never_seen":
        return "WAITING"
    return "DISCONNECTED"


def _pct(value):
    return f"{value:.1f} %"


def panel_rows(data, state):
    """Text for the UI panel as (label, value) pairs. Never shows old values as if they were live."""
    if data is None:
        return [("Connection", state), ("Data", "no data received yet")]
    suffix = "" if state == "LIVE" else "  (last known)"
    predicted = data.get("predicted_level_pct")
    horizon = data.get("horizon_s", 60)
    forecast = f"{_pct(predicted)} in {horizon} s" if predicted is not None else "not available yet"
    return [
        ("Connection", state),
        ("Water level", _pct(data["level_pct"]) + suffix),
        ("Inflow", f"{data['inflow_lpm']:.1f} L/min" + suffix),
        ("Outflow", f"{data['outflow_lpm']:.1f} L/min" + suffix),
        ("Pump", ("ON" if data["pump_on"] else "OFF") + suffix),
        ("AI forecast", forecast + (suffix if predicted is not None else "")),
        ("Rule alarm", str(data.get("alarm", "none")).replace("_", " ")),
        ("AI warning", str(data.get("ai_warning", "none")).replace("_", " ")),
        ("Data time (UTC)", str(data["timestamp"])),
    ]