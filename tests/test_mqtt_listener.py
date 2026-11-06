from types import SimpleNamespace

from mqtt_listener import TankListener


def msg(topic, payload):
    return SimpleNamespace(topic=topic, payload=payload)


def test_messages_go_into_queue_with_kind_and_time():
    l = TankListener()
    l._on_message(None, None, msg("twin/tank_01/enriched", b"{}"))
    l._on_message(None, None, msg("twin/tank_01/status", b"{}"))
    items = l.drain()
    assert [i[0] for i in items] == ["enriched", "status"]
    assert items[0][1] == b"{}" and items[0][2] > 0


def test_drain_empties_queue_and_never_blocks():
    l = TankListener()
    assert l.drain() == []
    l._on_message(None, None, msg("twin/tank_01/enriched", b"x"))
    assert len(l.drain()) == 1 and l.drain() == []


def test_full_queue_drops_oldest_keeps_newest():
    l = TankListener(max_queue=3)
    for i in range(5):
        l._on_message(None, None, msg("twin/tank_01/enriched", str(i).encode()))
    assert [i[1] for i in l.drain()] == [b"2", b"3", b"4"]
    assert l.dropped == 2


def test_bad_message_object_does_not_raise():
    TankListener()._on_message(None, None, object())


def test_connect_flags_and_subscribe():
    l = TankListener()
    calls = []
    client = SimpleNamespace(subscribe=lambda topics: calls.append(topics))
    l._on_connect(client, None, {}, 0, None)
    assert l.broker_connected and len(calls[0]) == 2
    l._on_disconnect(client, None, 0)
    assert not l.broker_connected