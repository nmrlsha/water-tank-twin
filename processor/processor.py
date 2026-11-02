"""Subscribes to raw tank messages, validates, stores, adds aggregates and a baseline
alarm, then publishes an enriched message.

Run:  python processor/processor.py
"""
import argparse
import json
import time

import paho.mqtt.client as mqtt

from aggregates import RollingStats
from alarm import rule_based_alarm
from storage import Storage
from validation import validate_message

RAW_TOPIC = "twin/tank_01/raw"
ENRICHED_TOPIC = "twin/tank_01/enriched"
HORIZON_S = 60


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--db", default="data/tank.db")
    args = parser.parse_args()

    storage = Storage(args.db)
    stats = RollingStats(window=60)
    counts = {"valid": 0, "rejected": 0}
    print(f"Database: {args.db} (already holds {storage.count()} rows)")

    def on_connect(client, userdata, flags, reason_code, properties):
        print(f"Connected to broker (reason: {reason_code})")
        client.subscribe(RAW_TOPIC)

    def on_message(client, userdata, msg):
        data, reason = validate_message(msg.payload)
        if data is None:
            counts["rejected"] += 1
            print(f"REJECTED ({reason}): {msg.payload[:80]!r}")
            return

        rolling = stats.update(data["level_pct"], data["inflow_lpm"])
        alarm = rule_based_alarm(data)

        try:
            storage.insert_state(data, alarm=alarm)
        except Exception as error:
            print(f"DATABASE ERROR: {error}")
            return
        counts["valid"] += 1

        enriched = {
            **data,
            **rolling,
            "predicted_level_pct": None,      # the AI model fills this in later
            "horizon_s": HORIZON_S,
            "alarm": alarm,
            "data_status": "ok",
        }
        client.publish(ENRICHED_TOPIC, json.dumps(enriched))

        print(f"SAVED  {data['timestamp']}  level={data['level_pct']:6.2f}%  "
              f"mean60={rolling['rolling_mean_level_pct']:6.2f}  alarm={alarm}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    print(f"Listening on {RAW_TOPIC}. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nStopped. saved={counts['valid']} rejected={counts['rejected']} "
              f"total_in_db={storage.count()}")
    finally:
        client.loop_stop()
        client.disconnect()
        storage.close()


if __name__ == "__main__":
    main()