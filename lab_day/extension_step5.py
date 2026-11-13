"""STEP 5 version of extension.py (UNTESTED inside Kit: verify on lab day).

Does four things:
  1. opens usd/tank_twin.usda by itself a couple of seconds after startup,
  2. reads the MQTT queue on every Kit update tick,
  3. moves the water / pump / light / forecast marker to match the data,
  4. shows a 'Tank Twin' panel window with values, forecast, trend, alarms and connection state.
Keep the template's class name if it differs from TankTwinExtension.
"""
import asyncio
import os
from pathlib import Path

import omni.ext
import omni.kit.app
import omni.usd

from .mqtt_listener import TankListener
from .panel import TankPanel
from .scene_apply import SceneApplier
from .twin_state import TwinState

OPEN_AFTER_FRAMES = 120      # about 2 seconds: lets Kit finish its own startup first
MODEL_NAME = "tank_twin.usda"


def find_model():
    """TANK_USD environment variable wins; otherwise look for usd/tank_twin.usda above this file."""
    override = os.environ.get("TANK_USD")
    if override:
        return Path(override)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "usd" / MODEL_NAME
        if candidate.exists():
            return candidate
    return None


class TankTwinExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[tank_twin] startup")
        self._listener = TankListener(host="127.0.0.1")
        self._state = TwinState()
        self._applier = None
        self._stage_id = None
        self._frames = 0
        self._opened = False
        self._last_conn = None
        self._messages = 0
        self._panel = TankPanel()
        self._panel_error_shown = False
        self._listener.start()
        stream = omni.kit.app.get_app().get_update_event_stream()
        self._sub = stream.create_subscription_to_pop(self._on_update, name="tank_twin_update")

    # ---- runs on Kit's update tick: the only place that touches the scene ----------
    def _on_update(self, event):
        self._frames += 1
        if not self._opened and self._frames >= OPEN_AFTER_FRAMES:
            self._open_model()

        changed = self._state.apply(self._listener.drain())
        self._prepare_applier()
        connection = self._state.connection()
        if self._applier and (changed or connection != self._last_conn):
            self._applier.apply(self._state.data, connection)
        if changed or connection != self._last_conn:
            self._update_panel()
        self._last_conn = connection

        if changed:
            self._messages += 1
            if self._messages % 10 == 1:
                delay = self._state.delay_summary()
                print("[tank_twin]", connection, f"delay={delay[0]:.2f}s" if delay else "")

    def _update_panel(self):
        try:
            self._panel.update(self._state)
        except Exception as error:               # a panel bug must never stop the 3D scene
            if not self._panel_error_shown:
                self._panel_error_shown = True
                print("[tank_twin] panel error:", repr(error))

    def _open_model(self):
        self._opened = True
        context = omni.usd.get_context()
        current = context.get_stage_url() or ""
        if current.endswith(MODEL_NAME):
            return                                   # already open (opened by hand)
        model = find_model()
        if model is None:
            print(f"[tank_twin] WARNING: usd/{MODEL_NAME} not found; open it by hand or set TANK_USD")
            return
        print(f"[tank_twin] opening {model}")
        asyncio.ensure_future(context.open_stage_async(str(model)))

    def _prepare_applier(self):
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        if id(stage) != self._stage_id:              # a new stage was opened: look again
            self._stage_id = id(stage)
            applier = SceneApplier(stage)
            if applier.ready:
                self._applier = applier
                print("[tank_twin] scene ready")
            else:
                self._applier = None
                print("[tank_twin] stage has no tank prims yet; missing:", applier.missing)

    def on_shutdown(self):
        print("[tank_twin] shutdown")
        self._sub = None
        self._listener.stop()
        if self._panel:
            self._panel.destroy()
            self._panel = None