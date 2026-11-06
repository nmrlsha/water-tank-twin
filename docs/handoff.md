# HANDOFF SUMMARY: Water Tank Digital Twin (continue from here)

## 0. How I want you to help (please follow)
- I'm a **total beginner**. Use **simple language**, explain **why** before each step, and keep tasks **small**.
- Say **exactly where** each file goes (folder + file name), what to run, what output to expect, and list common problems.
- Windows laptop, PowerShell, VS Code. Give one-line commands (I run them in the VS Code terminal).
- When possible, test code before giving it to me. Be honest about anything you cannot test (you cannot run Omniverse Kit; Kit API details must be verified against the docs on lab day).
- I like a recap when I'm lost. Ask at most one question at a time.

## 1. The assignment
University course "Digital Twin Project 2" (30% of the course). Build an AI-enabled digital twin with NVIDIA Omniverse Kit App Template. Group of 2. **Submission 16 Nov 2026; demos 17-20 Nov 2026.**
I chose **Option 3: Water tank and pump monitoring** (one tank, inlet pipe, outlet pipe, pump; stream level, inflow, outflow, pump state; regression model predicts the level at a fixed future horizon; show predicted level and an overflow/low-level warning; demonstrate filling, draining, abnormal inflow).
Five assessed components, 20% each: Development, Deployment, Visualization, AI/Behaviour model, Data storage & aggregation.
Key requirements from the guideline:
- Custom Kit app from the template + at least one custom Python extension; OpenUSD scene with named prims, correct scale, organised hierarchy; map each variable to a prim attribute/UI field; record modelling contributions, asset sources, tested Kit version / template commit / OS / GPU / dependencies.
- MQTT/HTTP/WebSocket with a documented schema; at least 4 variables + UTC timestamp + asset ID; ~1 Hz; report measured data-to-display delay (target <= 2 s). Network work must stay off the UI path; apply scene changes via the Kit update mechanism.
- Persistent DB (SQLite is enough) with raw values, timestamps and AI outputs, plus >= 2 aggregates.
- Lightweight AI model (not just a threshold alarm); show AI result, current state, a trend and an alarm indicator inside Kit. Split train/test by run (no random split), regression vs a persistence baseline (MAE/RMSE), held-out scenario, document synthetic-data limits, handle unavailable/invalid input.
- Five mandatory tests: normal operation; abnormal condition; stream interruption (show STALE/DISCONNECTED, recover); invalid input (no crash); restart and history (retrieve stored data, history plot/replay).
- Git with meaningful commits, sprint plan, unit + integration + regression tests with a test log (inputs, expected, actual, fixes); repeatable local deployment; **containerize at least two communicating backend services** (the Kit app itself is not containerized).
- Package: code + Git history, Kit config, extension, USD, simulator, schema, deploy files, README with exact startup steps, sample DB, dataset description + training script + saved model + evaluation, concise technical report (scope, architecture, implementation, visualization, AI evaluation, storage, testing, limitations, individual contributions), demo video (5-8 min) + live demo.
- My lecturer **mentioned Grafana** (not in the PDF). Earlier lab sessions **used InfluxDB** (version unknown). I'm not sure whether either is required, so I'm still asking. Decision so far: SQLite now; InfluxDB swap and Grafana are stretch goals.

## 2. My situation and constraints
- Laptop has **no RTX GPU**, so Kit can't run on it. The **lab RTX PC** is needed for Kit. **I have no lab access until 10 Nov** (so about 6 days with Kit before the deadline).
- Kit App Template was already built and launched once on the lab PC (it worked). I plan to retry with my own repo. The lab PC probably has Docker (we ran a docker-compose there before), to be confirmed with `docker --version` and `docker ps`.
- Windows **Application Control blocks compiled Python packages** (scikit-learn/SciPy fail with "DLL load failed ... blocked"). So I run ML and USD scripts **inside Docker** (`python:3.12-slim`). Laptop Python is 3.14; containers use 3.12. On the laptop only plain-Python things work (pytest, paho-mqtt).
- GitHub: private repo `nmrlsha/water-tank-twin`; I have a partner (should accept the invite; asked to retry the Kit setup in the lab).
- Terminal habits: use a normal (non-admin) PowerShell/VS Code terminal. The `.venv` is in the top-level folder (`.\.venv\Scripts\Activate.ps1`); run `docker compose` commands from `deploy/`. In PowerShell use `Invoke-RestMethod` (not `curl`). `git add .` -> `git commit -m "..."` -> `git push`.

## 3. Architecture
```
simulator.py --raw--> Mosquitto broker --raw--> processor (validate, predict, store, alarms, heartbeat)
                                                    |--enriched + status--> broker --> Kit extension (3D scene + UI panel)
                                                    |--> SQLite (docker volume) <--read-only-- REST API (port 8000) <-- Kit extension history plot
```
Docker Compose services (`deploy/docker-compose.yml`): `mosquitto` (port 1883), `processor`, `simulator`, `api` (port 8000); named volume `tank_data` (DB at `/app/data/tank.db` in processor, `/data/tank.db` in api). Containers reach the broker by service name `mosquitto`. After code changes: `docker compose up -d --build`. `docker compose down -v` deletes the DB, so avoid it.

## 4. Contracts (message formats)
MQTT topics: `twin/tank_01/raw` (simulator -> processor), `twin/tank_01/enriched` (processor -> Kit), `twin/tank_01/status` (processor/broker -> Kit; retained, 1 per second), `twin/tank_01/control` (plain-text simulator mode).
- **raw**: `{"asset_id":"tank_01","timestamp":"2026-11-02T08:00:00Z","level_pct":62.0,"inflow_lpm":4.2,"outflow_lpm":2.0,"pump_on":true}`; ranges: level 0-100, inflows 0-50; UTC timestamps `YYYY-MM-DDTHH:MM:SSZ`.
- **enriched** = raw fields + `rolling_mean_level_pct`, `rolling_max_inflow_lpm` (60-sample window), `predicted_level_pct` (null for the first ~30 s), `horizon_s` (60), `prediction_status` ("ok"/"unavailable"), `alarm` ("none"/"overflow_risk"/"low_level"/"abnormal_inflow"; threshold rules: >=90%, <=10%, inflow >=30), `ai_warning` ("none"/"overflow_expected"/"low_level_expected"/"unavailable"; from forecast >=90 / <=10), `data_status` ("ok").
- **status**: `asset_id, timestamp, processor ("online"/"offline"), source ("live"/"stale"/"never_seen"/"unknown"), seconds_since_last_data, last_data_timestamp, messages_valid, messages_rejected`. Source is "stale" after 5 s without a valid message. The broker publishes processor "offline" through an MQTT Last Will if the processor crashes.
- **control** modes for the simulator: `normal, abnormal_inflow, pump_failure, pump_stuck_on, stopped, invalid_data`.
- **SQLite table `tank_state`**: id, asset_id, timestamp, received_at, level_pct, inflow_lpm, outflow_lpm, pump_on (0/1), predicted_level_pct, alarm. WAL mode.
- **REST API** (read-only): `GET /health`, `/latest`, `/history?minutes=10&step=1&limit=2000` (oldest first), `/aggregates?minutes=10` (per-minute mean level, max inflow, alarm count, samples), `/alarms?minutes=60`; docs page at `/docs`; 503 if the DB does not exist yet.

## 5. Repository layout (all committed to GitHub)
- `README.md` (to-do + stretch list), `.gitignore` (ignores `.venv`, `*.db*`, `data/`, ...), `.dockerignore`, `pytest.ini` (`pythonpath = processor simulator ml api kit_extension`)
- `simulator/`: `tank_model.py` (physics: `TankSimulator(seed, level_pct, inflow_offset_lpm)`, 100 L tank, pump 20 L/min, on above 70% / off below 30%, nominal inflow 8, abnormal 40; scenarios normal/abnormal_inflow/pump_failure/pump_stuck_on), `simulator.py` (MQTT publisher at 1 Hz + control topic + stopped/invalid_data modes), `requirements.txt`, `Dockerfile`
- `processor/`: `validation.py`, `storage.py` (`Storage`: insert_state, count, latest, per_minute), `alarm.py` (`rule_based_alarm`, `ai_warning`), `aggregates.py` (`RollingStats`), `predictor.py` (`Predictor`, loads the joblib model, history reset after a gap > 5 s), `status.py` (`SourceMonitor`, `status_message`), `processor.py` (main loop; SIGTERM handled), `show_aggregates.py`, `requirements.txt` (pinned scikit-learn), `Dockerfile`
- `ml/`: `generate_dataset.py`, `features.py` (31-sample window, 14 features incl. net flow, horizon 60 s), `train_model.py` (candidates: linear regression, random forest, small MLP; `--models` filter; target = level change over 60 s), `requirements.txt`, `models/water_level_model.joblib`, `results/evaluation.json` (+ `evaluation_v1_level_target.json` and other saved variants)
- `api/`: `reader.py` (read-only `HistoryReader`), `main.py` (FastAPI), `requirements.txt` (need to pin versions), `Dockerfile`
- `usd/`: `build_tank.py` (procedural USD, metres, Y-up), `check_tank.py` (17 structure/pivot checks), `requirements.txt` (usd-core), `tank.usda`
- `kit_extension/`: `twin_logic.py` (Kit-free "brain", see section 7)
- `deploy/`: `docker-compose.yml`, `mosquitto.conf` (listener 1883, anonymous, no persistence)
- `tests/`: 10 test files, **76 tests passing** (validation 9, storage 5, alarm 9, aggregates 3, features 5, dataset generation 3, predictor 5, status 7, history reader 10, twin_logic 20)
- `docs/`: `schema.md`, `test_log.md`, `versions.md`, `decisions.md`, `contributions.md`, `evidence/` (screenshots)

## 6. AI results (final model: random forest on level CHANGE over 60 s)
Dataset: synthetic, generated from `tank_model.py` (fixed seeds; 30-minute runs; random start level, inflow offset, fault timetable, sensor noise). Split by run: train 40, val 8, test 10, plus a held-out scenario of 10 runs with `pump_stuck_on` (never seen in training). `scenario` column is never a feature.
- Validation MAE: linear 3.70%, random forest 2.59% (chosen on validation only), small neural net 2.61%, persistence 9.15%, trend rule 3.55%.
- **Test** (unseen runs): model MAE 2.92% / RMSE 5.06%; persistence 9.37 / 11.16; trend rule 3.83 / 7.14.
- **Held-out fault**: model MAE 6.06 / RMSE 9.26; persistence 8.15 / 8.93; trend rule 3.07 / 5.63. During `pump_stuck_on`: model 11.5 vs persistence 9.0 vs trend 3.4. Linear regression generalised better (MAE 5.89, RMSE 7.21); the MLP worst (9.66 / 15.0).
- **Overflow early warning** (60 s ahead, test): model precision 0.88, recall 0.81, F1 0.84; trend rule P 0.72 / R 0.99; threshold at 75%: P 0.35 / R 0.79; the current 90% alarm cannot warn early (0).
- v1 (predicting level directly) failed worse on the held-out fault (MAE 11.7); v2 (predict change + net-flow features) improved it (6.1) but is not fully fixed. Cause: tree models can't extrapolate to "pump on + low level", which never occurs in training; they learned the controller's habits.
- Honesty notes for the report: v2 was designed after seeing v1's held-out failure; the trend rule contains the simulator's exact tank size; all data is synthetic, so no real-world validity is claimed.
- Stretch ideas: residual learning (physics rule + AI correction), a fresh held-out set with new seeds, debouncing the AI warning (it may flicker near 90%).

## 7. The Kit extension plan (where I am now)
Objective: the extension runs inside Omniverse, listens to the backend, moves the 3D scene to match, and shows a panel with values, AI forecast and LIVE/STALE/DISCONNECTED status.
Steps: **1. Kit-free "brain" (DONE)**; 2. MQTT listener with background thread + thread-safe queue (testable on the laptop with the broker); 3. Create the Kit app + empty extension (lab); 4. Apply the brain to the scene (lab); 5. UI panel (lab); 6. History plot via the API, then polish.
`twin_logic.py` (done, tested) provides: prim paths `/World/Tank/Water` (scale Y = level/100, pivot on tank floor, min 0.001), `/World/Pump/Indicator` (green = pump on, grey = off), `/World/Tank/AlarmLight` (red = rule alarm, amber = AI warning, green = ok); `parse_message`, `is_valid_enriched`, `water_scale_y`, `pump_colour`, `alarm_level/alarm_colour`, `connection_state(status, status_age_s, timeout_s=5)` -> LIVE/STALE/WAITING/DISCONNECTED (processor offline or no status for 5 s = DISCONNECTED), `panel_rows(data, state)` (values get "(last known)" when not LIVE).
Known gotchas for the extension: `paho-mqtt` must be available inside Kit's own Python (declare in the extension config, a common stumbling block); MQTT callbacks must only put messages in a queue, and the scene is changed on the Kit update event; the extension should open `usd/tank.usda` (`omni.usd.get_context().open_stage(path)`) or I open it by hand; measure the delay as receive time minus the message timestamp; the extension connects to `127.0.0.1:1883` (backend runs on the lab PC with Docker) and the API at `http://127.0.0.1:8000`.
3D model facts: tank cylinder radius 0.20 m x height 0.80 m (about 100 L), translucent shell, inlet pipe (left, near top), outlet pipe + pump (right, near bottom), alarm light on the lid, camera + lights; built procedurally with `usd-core` (no downloaded assets). On the lab PC: `git pull`, launch the Kit app (`.\repo.bat launch`), File > Open `usd/tank.usda`, then try changing the water's Scale Y by hand to confirm it grows from the floor.

## 8. Still to do (rough priority)
1. Kit extension steps 2-6 (largest risk; write as much as possible before 10 Nov).
2. Lab day (10 Nov): confirm Docker; `git pull`; build the app from my repo; open the USD; print one MQTT message; then move the water; record Kit version, template commit, OS, GPU, driver in `docs/versions.md`.
3. Five mandatory test scenarios with screenshots; fill `docs/test_log.md` (T01-T08); measure the delay (<= 2 s target); integration test of the data path; regression check (`pytest`).
4. Evidence screenshots in `docs/evidence/` (compose ps, pytest, normal run, AI warning appearing before the threshold alarm with the lead time in seconds, status live/stale/recovered, invalid input, Last Will, restart/history, API docs and history). The restart/history evidence (rows 9,455 -> 9,480 -> 9,510 across restart and down/up) is done.
5. Pin API library versions (fastapi, uvicorn) and the other versions in `docs/versions.md`.
6. Sample database export, backup/redundancy evidence, architecture diagram, sprint plan, README with exact startup instructions.
7. Technical report in Word (+ PDF export; draft non-Kit sections early), demo video 5-8 min, live demo prep, contributions of each member.
8. Stretch: Grafana (SQLite plugin or Postgres), InfluxDB swap (`processor/storage.py` and the API reader are the only DB touchpoints), model residual learning.

## 9. Open questions
- Is Grafana/InfluxDB required or optional (ask the lecturer)? Report format Word vs PDF? Can I get earlier Kit access (another RTX machine)?
- Has my partner accepted the GitHub invite and progressed on the Kit setup? Does the lab PC's own login have working Docker (`docker --version`, `docker ps`)? If not, fallback: run the backend without Docker (needs Python, native Mosquitto, and scikit-learn loading on that PC).

## 10. Where we stopped
Backend is complete and tested (76 tests). The Kit extension "brain" (Step 1) is done. **Next: Step 2 of the extension, the MQTT listener (background thread + queue), testable on my laptop with the Docker broker.** Then prepare the extension code for the lab day and the report notes.