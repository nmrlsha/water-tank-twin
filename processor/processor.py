"""Subscribes to raw tank messages, validates them, predicts the level 60 s ahead,
stores everything in SQLite, adds aggregates and alarms, publishes an enriched message,
and publishes a status/heartbeat message once per second.

Runs inside Docker (see deploy/docker-compose.yml).
"""
import argparse
import json
import signal
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from aggregates import RollingStats
from alarm import ai_warning, rule_based_alarm
from predictor import Predictor
from status import STALE_AFTER_S, SourceMonitor, status_message
from storage import Storage
from validation import validate_message

ASSET_ID = "tank_01"
RAW_TOPIC = f"twin/{ASSET_ID}/raw"
ENRICHED_TOPIC = f"twin/{ASSET_ID}/enriched"
STATUS_TOPIC = f"twin/{ASSET_ID}/status"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--db", default="data/tank.db")
    parser.add_argument("--model", default="ml/models/water_level_model.joblib")
    parser.add_argument("--stale-after", type=float, default=STALE_AFTER_S,
                        help="seconds without a valid message before the source counts as stale")
    args = parser.parse_args()

    # docker compose stop sends SIGTERM: turn it into a normal, clean shutdown
    signal.signal(signal.SIGTERM, lambda signum, frame: (_ for _ in ()).throw(KeyboardInterrupt()))

    storage = Storage(args.db)
    stats = RollingStats(window=60)
    predictor = Predictor.from_file(args.model)
    monitor = SourceMonitor(args.stale_after)
    print(f"Database: {args.db} (already holds {storage.count()} rows)")
    print(f"Model loaded from {args.model} (horizon {predictor.horizon_s} s)")

    def publish_status(client, processor_state, with_snapshot=True):
        snapshot = monitor.snapshot(time.monotonic()) if with_snapshot else None
        message = status_message(ASSET_ID, utc_now(), processor_state, snapshot)
        client.publish(STATUS_TOPIC, json.dumps(message), qos=1, retain=True)
        return message

    def on_connect(client, userdata, flags, reason_code, properties):
        print(f"Connected to broker (reason: {reason_code})")
        client.subscribe(RAW_TOPIC)
        publish_status(client, "online")

    def on_message(client, userdata, msg):
        data, reason = validate_message(msg.payload)
        if data is None:
            monitor.record_rejected()
            print(f"REJECTED ({reason}): {msg.payload[:80]!r}")
            return
        monitor.record_valid(time.monotonic(), data["timestamp"])

        rolling = stats.update(data["level_pct"], data["inflow_lpm"])
        alarm = rule_based_alarm(data)
        try:
            predicted = predictor.update(data)
        except Exception as error:         # a model problem must not stop the processor
            print(f"PREDICTION ERROR: {error}")
            predicted = None
        warning = ai_warning(predicted)

        try:
            storage.insert_state(data, predicted_level_pct=predicted, alarm=alarm)
        except Exception as error:
            print(f"DATABASE ERROR: {error}")
            return

        enriched = {
            **data,
            **rolling,
            "predicted_level_pct": predicted,
            "horizon_s": predictor.horizon_s,
            "prediction_status": "ok" if predicted is not None else "unavailable",
            "alarm": alarm,
            "ai_warning": warning,
            "data_status": "ok",
        }
        client.publish(ENRICHED_TOPIC, json.dumps(enriched))

        shown = f"{predicted:6.2f}" if predicted is not None else "  n/a "
        print(f"SAVED  {data['timestamp']}  level={data['level_pct']:6.2f}%  "
              f"pred+{predictor.horizon_s}s={shown}%  alarm={alarm}  ai={warning}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    # Last Will: if this process dies without saying goodbye, the BROKER publishes this.
    client.will_set(STATUS_TOPIC, json.dumps(status_message(ASSET_ID, utc_now(), "offline")),
                    qos=1, retain=True)
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    print(f"Listening on {RAW_TOPIC}; heartbeat on {STATUS_TOPIC}. Press Ctrl+C to stop.")
    last_source = None
    try:
        while True:
            status = publish_status(client, "online")
            if status["source"] != last_source:                 # log only the changes
                print(f"SOURCE STATUS: {status['source']}")
                last_source = status["source"]
            time.sleep(1)
    except KeyboardInterrupt:
        snapshot = monitor.snapshot(time.monotonic())
        print(f"\nStopped. saved={snapshot['messages_valid']} rejected={snapshot['messages_rejected']} "
              f"total_in_db={storage.count()}")
    finally:
        publish_status(client, "offline", with_snapshot=False)  # clean exit: say so ourselves
        time.sleep(0.3)                                         # let the message leave
        client.loop_stop()
        client.disconnect()
        storage.close()


if __name__ == "__main__":
    main()