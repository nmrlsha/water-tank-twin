# Water Tank Digital Twin
Simulation-driven digital twin prototype of a water tank and pump (Omniverse + MQTT + SQLite + AI).

## Later / stretch goals
- [ ] If time allows: swap SQLite for InfluxDB. Only `processor/storage.py` needs replacing (same methods: insert_state, latest, count, per_minute). Check which InfluxDB version the lab used (1.x / 2.x / 3.x) first.
- [ ] Grafana dashboard (works with either database)
- [ ] Heartbeat on twin/tank_01/status (stale data detection)