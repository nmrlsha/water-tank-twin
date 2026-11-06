"""The 'ears' of the Kit extension: listens to MQTT on a BACKGROUND thread.

Rule: the MQTT callbacks only put messages into a queue. They never touch the
3D scene or the UI. The Kit update event later calls drain() to collect them.
No Kit imports here, so it runs on any laptop.
"""
import queue
import time

import paho.mqtt.client as mqtt

TOPIC_ENRICHED = "twin/{asset}/enriched"
TOPIC_STATUS = "twin/{asset}/status"


def _make_client():
    """paho-mqtt 2.x needs a callback API version; 1.x does not. Support both."""
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        return mqtt.Client()


class TankListener:
    def __init__(self, host="127.0.0.1", port=1883, asset_id="tank_01", max_queue=1000):
        self.host, self.port = host, port
        self.topic_enriched = TOPIC_ENRICHED.format(asset=asset_id)
        self.topic_status = TOPIC_STATUS.format(asset=asset_id)
        self._queue = queue.Queue(maxsize=max_queue)
        self.broker_connected = False
        self.dropped = 0
        self._client = _make_client()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=5)

    # ---- called from the Kit side -------------------------------------------
    def start(self):
        """Non-blocking. Keeps retrying in the background if the broker is down."""
        self._client.connect_async(self.host, self.port, keepalive=10)
        self._client.loop_start()

    def stop(self):
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except Exception:
            pass

    def drain(self):
        """Return every waiting item as a list of (kind, payload, received_at). Never blocks."""
        items = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                return items

    # ---- called from the MQTT background thread (keep these tiny and safe) ---
    def _on_connect(self, client, userdata, *args):
        # Subscribing here means we re-subscribe automatically after every reconnect.
        self.broker_connected = True
        client.subscribe([(self.topic_enriched, 0), (self.topic_status, 0)])

    def _on_disconnect(self, client, userdata, *args):
        self.broker_connected = False

    def _on_message(self, client, userdata, msg):
        try:
            kind = "enriched" if msg.topic == self.topic_enriched else "status"
            item = (kind, bytes(msg.payload), time.time())
            try:
                self._queue.put_nowait(item)
            except queue.Full:                    # drop the oldest, keep the newest
                self._queue.get_nowait()
                self._queue.put_nowait(item)
                self.dropped += 1
        except Exception:
            pass                                  # a callback must never crash the thread