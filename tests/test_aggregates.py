from aggregates import RollingStats


def test_rolling_mean_is_correct():
    s = RollingStats(window=3)
    s.update(10, 1)
    s.update(20, 1)
    result = s.update(30, 1)
    assert result["rolling_mean_level_pct"] == 20.0


def test_old_values_drop_out_of_window():
    s = RollingStats(window=3)
    for level in (10, 20, 30):
        s.update(level, 1)
    result = s.update(40, 1)            # window is now 20, 30, 40
    assert result["rolling_mean_level_pct"] == 30.0


def test_rolling_max_inflow():
    s = RollingStats(window=3)
    s.update(50, 5)
    result = s.update(50, 9)
    assert result["rolling_max_inflow_lpm"] == 9.0