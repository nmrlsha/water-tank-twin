"""The 'brain' of the Kit extension: turns messages into display decisions.

No Kit imports in this file, so it runs and is unit tested on any laptop.
The Kit extension (written later) only has to APPLY what this file decides.
"""
import json

# ---- Where things live in usd/tank_twin.usda (our own model, made in Omniverse) --------
# The tank is rotated -90 degrees about X, so the tank's LOCAL Z axis points UP in the world.
PRIM_WATER = "/World/Tank_01/Water"                    # scale Z  <- level (pivot on the tank floor)
PRIM_PUMP = "/World/Tank_01/Pump"                      # material <- pump on/off
PRIM_ALARM_LIGHT = "/World/Tank_01/WarningLight"       # material <- alarm / AI warning
PRIM_PREDICTION_MARKER = "/World/Tank_01/PredictionMarker"   # translate Z <- forecast level
PRIM_PUMP_LIGHT = PRIM_PUMP                            # old name, kept so older code still works

MAT_PUMP_ON = "/World/Looks/Mat_PumpOn"
MAT_PUMP_OFF = "/World/Looks/Mat_PumpOff"
MAT_LIGHT = {"ok": "/World/Looks/Mat_LightGreen",
             "warning": "/World/Looks/Mat_LightAmber",
             "alarm": "/World/Looks/Mat_LightRed"}

TANK_HEIGHT_M = 0.8                           # water fills z = 0 .. 0.8 in the tank's local frame
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

# ---- Helpers for the model with material switching (tank_twin.usda) -----------------
def water_scale_vector(level_pct):
    """Scale for the Water prim as (x, y, z). Only Z changes, because Z is 'up' for the tank."""
    return (1.0, 1.0, water_scale_y(level_pct))


def pump_material(pump_on):
    return MAT_PUMP_ON if pump_on else MAT_PUMP_OFF


def alarm_material(data):
    return MAT_LIGHT[alarm_level(data)]


def prediction_marker_z(predicted_level_pct):
    """Height of the forecast marker in metres, or None when there is no usable forecast."""
    try:
        value = float(predicted_level_pct)
    except (TypeError, ValueError):
        return None
    if value != value:                       # NaN
        return None
    return TANK_HEIGHT_M * max(0.0, min(100.0, value)) / 100.0


def light_material(data, state):
    """Material for the warning light. Grey when the feed is not LIVE, so old data never looks healthy."""
    if state != "LIVE" or data is None:
        return MAT_PUMP_OFF                   # the model's grey material
    return alarm_material(data)