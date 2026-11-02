"""Turns the last 30 seconds of readings into the numbers the model uses.

Used by BOTH training and the live processor, so they can never disagree.
"""

WINDOW = 31          # the current reading + the 30 before it (30 s of history at 1 Hz)
HORIZON_S = 60       # how far ahead we predict

FEATURE_NAMES = [
    "level_now", "inflow_now", "outflow_now", "pump_now",
    "level_change_10s", "level_change_30s",
    "mean_inflow_10s", "mean_outflow_10s",
    "mean_inflow_30s", "mean_outflow_30s",
    "pump_on_fraction_30s",
    "net_flow_now", "mean_net_flow_10s", "mean_net_flow_30s",
]


def _mean(values):
    return sum(values) / len(values)


def build_features(window):
    """window: list of readings (oldest first), each with level_pct, inflow_lpm,
    outflow_lpm, pump_on. Returns a list of numbers, or None if there isn't
    enough history yet."""
    if len(window) < WINDOW:
        return None
    w = window[-WINDOW:]
    levels = [r["level_pct"] for r in w]
    inflows = [r["inflow_lpm"] for r in w]
    outflows = [r["outflow_lpm"] for r in w]
    pumps = [1.0 if r["pump_on"] else 0.0 for r in w]
    nets = [i - o for i, o in zip(inflows, outflows)]       # litres/min gained (+) or lost (-)
    return [
        levels[-1], inflows[-1], outflows[-1], pumps[-1],
        levels[-1] - levels[-11],            # change over the last 10 s
        levels[-1] - levels[0],              # change over the last 30 s
        _mean(inflows[-10:]), _mean(outflows[-10:]),
        _mean(inflows), _mean(outflows),
        _mean(pumps),
        nets[-1], _mean(nets[-10:]), _mean(nets),
    ]