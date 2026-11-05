# Design Decisions

| Decision | Alternatives | Why |
|---|---|---|
| SQLite for storage | InfluxDB | Allowed by the guideline, no extra service, enough for 1 Hz data; InfluxDB kept as a stretch goal |
| Predict level change, not level | Predict level directly | v1 learned the pump controller's habits and failed on an unseen fault; v2 improved generalisation |
| Random forest as final model | Linear regression, small neural network | Lowest validation MAE; selection made on validation runs only |
| Split data by run | Random 80/20 split | Consecutive seconds are near-identical, so random splits leak |
| Stale threshold 5 s | Other values | 5 missed samples at 1 Hz; configurable |
| Three-layer disconnect detection | Single heartbeat | Processor handles the dead source, Last Will handles a dead processor, extension handles a dead broker |
| Extension logic in a separate Kit-free file | Put everything in the Kit extension | Can be unit tested on a laptop without a GPU; the extension only applies the decisions |