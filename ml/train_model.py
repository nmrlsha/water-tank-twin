"""Train and evaluate the water level model, v2.

The model predicts the CHANGE in level over the next 60 s; the final prediction is
level_now + predicted change (kept between 0 and 100).

Run from the top-level folder:  python ml/train_model.py
Needs data/dataset.csv from:    python ml/generate_dataset.py
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (confusion_matrix, mean_absolute_error, mean_squared_error,
                             precision_recall_fscore_support)

from features import FEATURE_NAMES, HORIZON_S, WINDOW, build_features

DATASET = Path("data/dataset.csv")
MODEL_PATH = Path("ml/models/water_level_model.joblib")
RESULTS_PATH = Path("ml/results/evaluation.json")
OVERFLOW_PCT = 90.0
EARLY_THRESHOLD_PCT = 75.0
IDX_LEVEL = FEATURE_NAMES.index("level_now")
IDX_NET10 = FEATURE_NAMES.index("mean_net_flow_10s")


def load_runs(path):
    runs = defaultdict(list)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            runs[(row["split"], row["run_id"])].append({
                "level_pct": float(row["level_pct"]),
                "inflow_lpm": float(row["inflow_lpm"]),
                "outflow_lpm": float(row["outflow_lpm"]),
                "pump_on": int(row["pump_on"]),
                "scenario": row["scenario"],
            })
    return runs


def make_samples(runs, split):
    """Turn each run into (features, level 60 s later, scenario). Windows never cross runs."""
    X, y, scenarios = [], [], []
    for (run_split, _), rows in runs.items():
        if run_split != split:
            continue
        for i in range(WINDOW - 1, len(rows) - HORIZON_S):
            X.append(build_features(rows[i - WINDOW + 1: i + 1]))
            y.append(rows[i + HORIZON_S]["level_pct"])
            scenarios.append(rows[i + HORIZON_S]["scenario"])    # analysis only, never an input
    return np.array(X), np.array(y), np.array(scenarios)


def predict_level(model, X):
    """Level now + predicted change, kept inside the physical range 0..100."""
    return np.clip(X[:, IDX_LEVEL] + model.predict(X), 0.0, 100.0)


def persistence(X):
    return X[:, IDX_LEVEL]


def trend_extrapolation(X):
    """Physics-aware baseline: current net flow continues for the whole horizon.
    Assumes a 100 L tank, so 1 L/min of net flow = 1 % of level per minute."""
    return np.clip(X[:, IDX_LEVEL] + X[:, IDX_NET10] * HORIZON_S / 60.0, 0.0, 100.0)


def error_metrics(y_true, y_pred):
    return {"mae": round(float(mean_absolute_error(y_true, y_pred)), 3),
            "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 3)}


def early_warning(y_true, level_now, flags):
    """Overflow early warning on samples NOT yet in overflow (level_now < 90).
    Positive = the level really will be >= 90 % sixty seconds from now."""
    mask = level_now < OVERFLOW_PCT
    actual = y_true[mask] >= OVERFLOW_PCT
    out = {"samples": int(mask.sum()), "real_overflows_ahead": int(actual.sum())}
    for name, flagged in flags.items():
        f = flagged[mask]
        p, r, f1, _ = precision_recall_fscore_support(actual, f, average="binary", zero_division=0)
        tn, fp, fn, tp = confusion_matrix(actual, f, labels=[False, True]).ravel()
        out[name] = {"precision": round(float(p), 3), "recall": round(float(r), 3),
                     "f1": round(float(f1), 3), "tp": int(tp), "fp": int(fp),
                     "fn": int(fn), "tn": int(tn)}
    return out


def main():
    if not DATASET.exists():
        raise SystemExit("data/dataset.csv not found. Run: python ml/generate_dataset.py")

    runs = load_runs(DATASET)
    data = {name: make_samples(runs, name) for name in ("train", "val", "test", "heldout_scenario")}
    X_train, y_train, _ = data["train"]
    delta_train = y_train - X_train[:, IDX_LEVEL]             # the target: change in level
    print("Samples:", {name: len(d[1]) for name, d in data.items()})

    candidates = {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=50, max_depth=8, min_samples_leaf=20,
                                               n_jobs=-1, random_state=42),
    }

    # 1. Train both, choose on VALIDATION runs only
    X_val, y_val, _ = data["val"]
    val_scores = {}
    print("\nValidation (used to pick the model):")
    for name, model in candidates.items():
        model.fit(X_train, delta_train)
        val_scores[name] = error_metrics(y_val, predict_level(model, X_val))
        print(f"  {name:18s} MAE={val_scores[name]['mae']:.3f}%  RMSE={val_scores[name]['rmse']:.3f}%")
    print(f"  {'persistence':18s} MAE={error_metrics(y_val, persistence(X_val))['mae']:.3f}%")
    print(f"  {'trend_extrapolation':18s} MAE={error_metrics(y_val, trend_extrapolation(X_val))['mae']:.3f}%")
    best_name = min(val_scores, key=lambda n: val_scores[n]["mae"])
    best = candidates[best_name]
    print(f"Chosen model: {best_name}")

    # 2. Final scores on data the model has never seen
    results = {"version": "v2_delta_target", "model": best_name, "horizon_s": HORIZON_S,
               "window_s": WINDOW - 1, "features": FEATURE_NAMES,
               "train_samples": int(len(y_train)), "validation": val_scores, "evaluation": {}}
    for split in ("test", "heldout_scenario"):
        X, y, scen = data[split]
        pred = predict_level(best, X)
        entry = {"samples": int(len(y)),
                 "model": error_metrics(y, pred),
                 "persistence_baseline": error_metrics(y, persistence(X)),
                 "trend_baseline": error_metrics(y, trend_extrapolation(X)),
                 "all_candidates_for_information": {
                     n: error_metrics(y, predict_level(m, X)) for n, m in candidates.items()},
                 "by_scenario_at_target": {}}
        for s in sorted(set(scen)):
            m = scen == s
            entry["by_scenario_at_target"][s] = {
                "samples": int(m.sum()),
                "model": error_metrics(y[m], pred[m]),
                "persistence_baseline": error_metrics(y[m], persistence(X[m])),
                "trend_baseline": error_metrics(y[m], trend_extrapolation(X[m]))}
        if split == "test":
            entry["overflow_early_warning"] = early_warning(y, X[:, IDX_LEVEL], {
                "model": pred >= OVERFLOW_PCT,
                "trend_extrapolation": trend_extrapolation(X) >= OVERFLOW_PCT,
                f"threshold_{int(EARLY_THRESHOLD_PCT)}": X[:, IDX_LEVEL] >= EARLY_THRESHOLD_PCT,
                "threshold_90_current_alarm": X[:, IDX_LEVEL] >= OVERFLOW_PCT})
        results["evaluation"][split] = entry

        print(f"\n=== {split} ({len(y)} samples) ===")
        for label, key in (("model", "model"), ("persistence", "persistence_baseline"),
                           ("trend", "trend_baseline")):
            print(f"  {label:12s} MAE={entry[key]['mae']:.3f}%  RMSE={entry[key]['rmse']:.3f}%")
        for s, v in entry["by_scenario_at_target"].items():
            print(f"    {s:16s} n={v['samples']:6d}  model MAE={v['model']['mae']:.3f}  "
                  f"persistence={v['persistence_baseline']['mae']:.3f}  trend={v['trend_baseline']['mae']:.3f}")
        if split == "heldout_scenario":
            print("  (for information only, the choice was made on validation):")
            for n, sc in entry["all_candidates_for_information"].items():
                print(f"    {n:18s} MAE={sc['mae']:.3f}%  RMSE={sc['rmse']:.3f}%")

    ew = results["evaluation"]["test"]["overflow_early_warning"]
    print("\nOverflow early warning on test runs (60 s ahead, level not yet >= 90%):")
    print(f"  real overflows ahead: {ew['real_overflows_ahead']} of {ew['samples']} samples")
    for name in ("model", "trend_extrapolation", f"threshold_{int(EARLY_THRESHOLD_PCT)}",
                 "threshold_90_current_alarm"):
        e = ew[name]
        print(f"  {name:27s} precision={e['precision']:.3f} recall={e['recall']:.3f} "
              f"f1={e['f1']:.3f} (tp={e['tp']} fp={e['fp']} fn={e['fn']})")

    if hasattr(best, "feature_importances_"):
        print("\nMost important features:")
        for imp, name in sorted(zip(best.feature_importances_, FEATURE_NAMES), reverse=True)[:5]:
            print(f"  {name:22s} {imp:.3f}")

    # 3. Save the model and the results
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": best, "name": best_name, "feature_names": FEATURE_NAMES,
                 "window": WINDOW, "horizon_s": HORIZON_S,
                 "target": "delta_level_pct"},      # prediction = level_now + model output, clipped to 0..100
                MODEL_PATH, compress=3)
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nSaved model to {MODEL_PATH} and results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()