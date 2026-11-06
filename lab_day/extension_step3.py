"""STEP 3 TEST VERSION of the extension (UNTESTED inside Kit: verify on lab day).

Goal: prove that Kit can import paho-mqtt, connect to the broker, and print messages.
No scene changes, no window yet.
Paste the body into the extension.py that 'repo template new' generated for you,
keeping the class name and the 'import omni.ext' line from the template.
"""
import omni.ext
import omni.kit.app

from .mqtt_listener import TankListener
from .twin_state import TwinState


class TankTwinExtension(omni.ext.IExt):          # <- keep YOUR template's class name
    def on_startup(self, ext_id):
        print("[tank_twin] startup")
        self._listener = TankListener(host="127.0.0.1")
        self._state = TwinState()
        self._shown = 0
        self._listener.start()                   # background thread, does not block Kit
        stream = omni.kit.app.get_app().get_update_event_stream()
        self._sub = stream.create_subscription_to_pop(self._on_update, name="tank_twin_update")

    def _on_update(self, event):
        # Runs on Kit's update tick: safe place to read the queue and (later) change the scene.
        if self._state.apply(self._listener.drain()):
            self._shown += 1
            if self._shown % 5 == 1:             # print every 5th message only
                print("[tank_twin]", self._state.connection(), dict(self._state.rows()))

    def on_shutdown(self):
        print("[tank_twin] shutdown")
        self._sub = None
        self._listener.stop()