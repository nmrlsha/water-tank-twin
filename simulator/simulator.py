"""Publishes simulated water tank states to MQTT once per second.

Run:      python simulator/simulator.py
Control:  publish a mode name to twin/tank_01/control to change behaviour live.
Modes:    normal, abnormal_inflow, pump_failure, pump_stuck_on,
          stopped (publish nothing), invalid_data (publish bad messages now and then)
"""
import argparse
import json
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from tank_model import SCENARIOS, TankSimulator

ASSET_ID = "tank_01"
RAW_TOPIC = f"twin/{ASSET_ID}/raw"
CONTROL_TOPIC = f"twin/{ASSET_ID}/control"
MODES = SCENARIOS + ("stopped", "invalid_data")


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_bad_message(good_payload, tick):
    """Return a deliberately broken message to test the processor's validation."""
    kind = tick % 4
    if kind == 0:
        return json.dumps({**good_payload, "level_pct": 150.0})      # out of range
    if kind == 1:
        bad = dict(good_payload)
        del bad["inflow_lpm"]                                          # missing field
        return json.dumps(bad)
    if kind == 2:
        return "this is not json"                                      # malformed
    return json.dumps({**good_payload, "inflow_lpm": -5.0})           # negative flow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--mode", default="normal", choices=MODES)
    parser.add_argument("--rate", type=float, default=1.0, help="messages per second")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    sim = TankSimulator(seed=args.seed)
    state = {"mode": args.mode}

    def on_connect(client, userdata, flags, reason_code, properties):
        print(f"Connected to broker (reason: {reason_code})")
        client.subscribe(CONTROL_TOPIC)   # subscribing here re-subscribes after any reconnect

    def on_message(client, userdata, msg):
        new_mode = msg.payload.decode(errors="ignore").strip()
        if new_mode in MODES:
            state["mode"] = new_mode
            print(f"Mode changed to: {new_mode}")
        else:
            print(f"Ignored unknown mode: {new_mode!r}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()   # network handling runs in a background thread

    interval = 1.0 / args.rate
    next_tick = time.monotonic()
    tick = 0
    print(f"Publishing to {RAW_TOPIC} every {interval:.2f}s. Press Ctrl+C to stop.")
    try:
        while True:
            mode = state["mode"]
            if mode in SCENARIOS:
                sim.set_scenario(mode)
            readings = sim.step(dt=interval)
            payload = {"asset_id": ASSET_ID, "timestamp": utc_now_iso(), **readings}

            if mode == "stopped":
                pass                                        # simulate a dead sensor link
            elif mode == "invalid_data" and tick % 3 == 0:
                client.publish(RAW_TOPIC, make_bad_message(payload, tick))
            else:
                client.publish(RAW_TOPIC, json.dumps(payload))
                print(payload)

            tick += 1
            next_tick += interval                           # fixed schedule, so no drift
            time.sleep(max(0.0, next_tick - time.monotonic()))
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()