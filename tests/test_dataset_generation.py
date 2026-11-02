from generate_dataset import RUN_LENGTH_S, simulate_run

FAULTS = ("abnormal_inflow", "pump_failure")


def test_same_seed_gives_identical_run():
    assert simulate_run("train", 7, FAULTS) == simulate_run("train", 7, FAULTS)


def test_different_seed_gives_different_run():
    assert simulate_run("train", 7, FAULTS) != simulate_run("train", 8, FAULTS)


def test_run_has_one_row_per_second():
    rows = simulate_run("train", 3, FAULTS)
    assert len(rows) == RUN_LENGTH_S
    assert [r["t_s"] for r in rows] == list(range(RUN_LENGTH_S))