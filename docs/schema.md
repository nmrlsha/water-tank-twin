# Water Tank Digital Twin: Message Schema

## 1. State dictionary (raw message)

| Field       | Type   | Unit             | Valid range   | Meaning                    |
|-------------|--------|------------------|---------------|----------------------------|
| asset_id    | string | none             | "tank_01"     | Which asset sent this      |
| timestamp   | string | ISO 8601 UTC     | valid time    | When the reading was taken |
| level_pct   | float  | % of tank height | 0 to 100      | Water level                |
| inflow_lpm  | float  | litres/min       | 0 to 50       | Water entering the tank    |
| outflow_lpm | float  | litres/min       | 0 to 50       | Water leaving the tank     |
| pump_on     | bool   | none             | true or false | Pump state                 |

Example:

```json
{"asset_id":"tank_01","timestamp":"2026-11-02T08:00:00Z","level_pct":62.0,"inflow_lpm":4.2,"outflow_lpm":2.0,"pump_on":true}
```

Valid ranges are used by the processor to reject bad input.

## 2. MQTT topics

| Topic                 | Publisher | Subscriber    | Content                                 |
|-----------------------|-----------|---------------|-----------------------------------------|
| twin/tank_01/raw      | Simulator | Processor     | Raw message above                       |
| twin/tank_01/enriched | Processor | Kit extension | Raw fields plus AI and aggregates       |
| twin/tank_01/status   | Processor | Kit extension | Heartbeat, used to detect disconnection |

The Kit extension only listens to `enriched` and `status`. It never talks to the simulator directly, so the simulator can later be replaced by a real sensor.

## 3. Enriched message (adds these fields)

| Field                  | Meaning                                                   |
|------------------------|-----------------------------------------------------------|
| predicted_level_pct    | AI forecast of level at the horizon                       |
| horizon_s              | How far ahead the forecast is, e.g. 60 seconds            |
| rolling_mean_level_pct | Mean level over the last 60 samples                       |
| alarm                  | "none", "overflow_risk", "low_level" or "abnormal_inflow" |
| data_status            | "ok" or "invalid"                                         |

## 4. SQLite table

```sql
CREATE TABLE IF NOT EXISTS tank_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,          -- UTC ISO 8601
    level_pct REAL, inflow_lpm REAL, outflow_lpm REAL,
    pump_on INTEGER,
    predicted_level_pct REAL,
    alarm TEXT
);
CREATE INDEX IF NOT EXISTS idx_time ON tank_state(asset_id, timestamp);
```

Enable WAL mode (`PRAGMA journal_mode=WAL;`) so the processor can write while Grafana reads.

## 5. Key decisions

- Sampling rate: 1 Hz
- Prediction horizon: 60 seconds ahead
- AI task: regression, predicting level_pct 60 s ahead from the last 30 to 60 samples
- Baseline: persistence (assume the level stays the same)
- Aggregates: rolling mean level, alarm count per minute, max inflow
- Acceptance criteria: data-to-display delay under 2 s; model MAE below the persistence baseline