"""Generate the dataset by running the tank model many times (no MQTT, much faster than real time).

Run from the top-level folder:  python ml/generate_dataset.py
Output: data/dataset.csv  (reproducible: the same seeds always give the same file)
"""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "simulator"))
from tank_model import TankSimulator  # noqa: E402

RUN_LENGTH_S = 1800                    # 30 minutes per run, 1 reading per second
OUTPUT = Path("data/dataset.csv")

# split name -> (first seed, number of runs, faults that may appear in that split)
SPLITS = {
    "train": (0, 40, ("abnormal_inflow", "pump_failure")),
    "val": (100, 8, ("abnormal_inflow", "pump_failure")),
    "test": (200, 10, ("abnormal_inflow", "pump_failure")),
    "heldout_scenario": (300, 10, ("pump_stuck_on",)),    # never seen in training
}


def make_schedule(rng, faults):
    """List of (scenario, duration_s) that fills one run: normal, fault, normal, fault..."""
    if rng.random() < 0.2:                                # 20% of runs are fault-free
        return [("normal", RUN_LENGTH_S)]
    schedule, used, next_is_fault = [], 0, False
    while used < RUN_LENGTH_S:
        if next_is_fault:
            scenario, duration = rng.choice(faults), rng.randint(60, 400)
        else:
            scenario, duration = "normal", rng.randint(100, 500)
        duration = min(duration, RUN_LENGTH_S - used)
        schedule.append((scenario, duration))
        used += duration
        next_is_fault = not next_is_fault
    return schedule


def simulate_run(split, seed, faults):
    rng = random.Random(seed + 10_000)                    # separate from the simulator's own noise
    sim = TankSimulator(seed=seed,
                        level_pct=rng.uniform(10, 90),
                        inflow_offset_lpm=rng.uniform(-3, 3))
    rows, t = [], 0
    for scenario, duration in make_schedule(rng, faults):
        sim.set_scenario(scenario)
        for _ in range(duration):
            r = sim.step(dt=1.0)
            rows.append({
                "split": split, "run_id": f"{split}_{seed}", "t_s": t,
                "scenario": scenario,                     # for analysis only, NEVER a model input
                "level_pct": r["level_pct"], "inflow_lpm": r["inflow_lpm"],
                "outflow_lpm": r["outflow_lpm"], "pump_on": int(r["pump_on"]),
            })
            t += 1
    return rows


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ["split", "run_id", "t_s", "scenario", "level_pct", "inflow_lpm", "outflow_lpm", "pump_on"]
    total = 0
    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for split, (first_seed, n_runs, faults) in SPLITS.items():
            count = 0
            for seed in range(first_seed, first_seed + n_runs):
                rows = simulate_run(split, seed, faults)
                writer.writerows(rows)
                count += len(rows)
            print(f"{split:18s} {n_runs:3d} runs  {count:7d} rows")
            total += count
    print(f"Wrote {total} rows to {OUTPUT}")


if __name__ == "__main__":
    main()