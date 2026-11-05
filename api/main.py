"""REST API for the water tank digital twin history.

Endpoints:  /health   /latest   /history   /aggregates   /alarms
Docs page:  http://localhost:8000/docs
"""
import os

from fastapi import FastAPI, HTTPException, Query

from reader import MAX_POINTS, DatabaseUnavailable, HistoryReader

ASSET_ID = "tank_01"
DB_PATH = os.environ.get("TANK_DB", "/data/tank.db")

app = FastAPI(title="Water tank twin: history API", version="0.1.0")
reader = HistoryReader(DB_PATH)


def _guard(call):
    try:
        return call()
    except DatabaseUnavailable:
        raise HTTPException(status_code=503, detail="database not available yet")


@app.get("/health")
def health():
    latest = _guard(lambda: reader.latest(ASSET_ID))
    return {"status": "ok", "asset_id": ASSET_ID,
            "rows": _guard(lambda: reader.count(ASSET_ID)),
            "latest_timestamp": latest["timestamp"] if latest else None}


@app.get("/latest")
def latest():
    row = _guard(lambda: reader.latest(ASSET_ID))
    if row is None:
        raise HTTPException(status_code=404, detail="no data stored yet")
    return row


@app.get("/history")
def history(minutes: int = Query(10, ge=1, le=1440),
            step: int = Query(1, ge=1, le=3600),
            limit: int = Query(2000, ge=1, le=MAX_POINTS)):
    points = _guard(lambda: reader.history(ASSET_ID, minutes, step, limit))
    return {"asset_id": ASSET_ID, "minutes": minutes, "step": step,
            "count": len(points), "points": points}


@app.get("/aggregates")
def aggregates(minutes: int = Query(10, ge=1, le=1440)):
    rows = _guard(lambda: reader.per_minute(ASSET_ID, minutes))
    return {"asset_id": ASSET_ID, "minutes": minutes, "per_minute": rows}


@app.get("/alarms")
def alarms(minutes: int = Query(60, ge=1, le=1440)):
    return {"asset_id": ASSET_ID, "minutes": minutes,
            "counts": _guard(lambda: reader.alarm_counts(ASSET_ID, minutes))}