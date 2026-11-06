"""Laptop test: prints what the Kit extension WOULD see, once per second.
Run from the top-level folder:  python kit_extension/listen_demo.py
Stop with Ctrl+C.
"""
import sys
import time

from mqtt_listener import TankListener
from twin_state import TwinState

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
listener, state = TankListener(host=host), TwinState()
listener.start()
try:
    while True:
        time.sleep(1.0)
        state.apply(listener.drain())            # in Kit this happens in the update event
        rows = dict(state.rows())
        delay = state.delay_summary()
        delay_text = f"{delay[0]:.2f}s (mean {delay[1]:.2f}s)" if delay else "-"
        print(f"{state.connection():12} broker={'up' if listener.broker_connected else 'down':4} "
              f"level={rows.get('Water level', '-'):>22} forecast={rows.get('AI forecast', '-'):>22} "
              f"delay={delay_text} rejected={state.rejected}")
except KeyboardInterrupt:
    listener.stop()