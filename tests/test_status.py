from status import SourceMonitor, status_message


def test_source_never_seen_before_any_data():
    snap = SourceMonitor(5.0).snapshot(now_mono=100.0)
    assert snap["source"] == "never_seen"
    assert snap["seconds_since_last_data"] is None


def test_source_is_live_right_after_a_valid_message():
    m = SourceMonitor(5.0)
    m.record_valid(100.0, "2026-11-02T08:00:00Z")
    snap = m.snapshot(now_mono=101.0)
    assert snap["source"] == "live"
    assert snap["seconds_since_last_data"] == 1.0
    assert snap["last_data_timestamp"] == "2026-11-02T08:00:00Z"


def test_source_becomes_stale_after_the_threshold():
    m = SourceMonitor(5.0)
    m.record_valid(100.0, "2026-11-02T08:00:00Z")
    assert m.snapshot(now_mono=105.0)["source"] == "live"       # exactly at the limit is still live
    assert m.snapshot(now_mono=105.1)["source"] == "stale"


def test_source_recovers_when_data_resumes():
    m = SourceMonitor(5.0)
    m.record_valid(100.0, "2026-11-02T08:00:00Z")
    assert m.snapshot(now_mono=200.0)["source"] == "stale"
    m.record_valid(200.0, "2026-11-02T08:01:40Z")
    assert m.snapshot(now_mono=200.5)["source"] == "live"


def test_rejected_messages_are_counted_but_do_not_make_the_source_live():
    m = SourceMonitor(5.0)
    m.record_rejected()
    m.record_rejected()
    snap = m.snapshot(now_mono=10.0)
    assert snap["messages_rejected"] == 2
    assert snap["source"] == "never_seen"


def test_status_message_contains_the_agreed_fields():
    m = SourceMonitor(5.0)
    m.record_valid(1.0, "2026-11-02T08:00:00Z")
    msg = status_message("tank_01", "2026-11-02T08:00:01Z", "online", m.snapshot(1.5))
    for field in ("asset_id", "timestamp", "processor", "source",
                  "seconds_since_last_data", "messages_valid", "messages_rejected"):
        assert field in msg
    assert msg["processor"] == "online"


def test_offline_message_has_unknown_source():
    msg = status_message("tank_01", "2026-11-02T08:00:01Z", "offline")
    assert msg["processor"] == "offline"
    assert msg["source"] == "unknown"