# Test Log

| ID | Scenario | Input / action | Expected | Actual | Result | Fix / note | Evidence |
|---|---|---|---|---|---|---|---|
| T01 | Normal operation | Run simulator in `normal` mode | Valid rows stored every second, predictions after 30 s | | | | |
| T02 | Abnormal condition | Send `abnormal_inflow` | `alarm=abnormal_inflow`, then `ai=overflow_expected` before `alarm=overflow_risk` | | | | |
| T03 | Stream interruption | Send `stopped` | Status `source=stale` within about 5 s; recovers on `normal` | | | | |
| T04 | Invalid input | Send `invalid_data` | Bad messages rejected with a reason, processor keeps running | | | | |
| T05 | Restart and history | `docker compose restart processor`, then `down` and `up` | Row count keeps growing, `/history` returns old data | | | | |
| T06 | Processor crash | `docker compose kill processor` | Broker publishes `processor=offline` (Last Will) | | | | |
| T07 | Unit tests | `pytest -v` | All pass | | | | |
| T08 | Data-to-display delay | (measured later in Kit) | At most 2 s at 1 Hz | | | | |