"""Applies display decisions to the 3D scene (needs pxr, which Kit provides).

Changes are written to the SESSION layer, so the saved tank_twin.usda is never modified
by live data. Call apply() from Kit's update event only (never from the MQTT thread).
"""
from pxr import Gf, Usd, UsdGeom, UsdShade

try:                                   # inside Kit this file is part of a package
    from . import twin_logic as logic
except ImportError:                    # on the laptop / pytest it is a plain module
    import twin_logic as logic


_NEVER = object()                      # 'nothing written yet' (different from a written None)


class SceneApplier:
    def __init__(self, stage):
        self.stage = stage
        self._last = {}                # what we last wrote, so we only write changes
        self.missing = [p for p in (logic.PRIM_WATER, logic.PRIM_PUMP, logic.PRIM_ALARM_LIGHT,
                                    logic.PRIM_PREDICTION_MARKER)
                        if not stage.GetPrimAtPath(p).IsValid()]

    @property
    def ready(self):
        return not self.missing

    def _changed(self, key, value):
        if self._last.get(key, _NEVER) == value:
            return False
        self._last[key] = value
        return True

    def _bind(self, prim_path, material_path):
        prim = self.stage.GetPrimAtPath(prim_path)
        material = UsdShade.Material(self.stage.GetPrimAtPath(material_path))
        if prim.IsValid() and material:
            UsdShade.MaterialBindingAPI(prim).Bind(material)

    def apply(self, data, state):
        """data = latest valid enriched message (or None); state = LIVE/STALE/... string."""
        if not self.ready:
            return
        with Usd.EditContext(self.stage, self.stage.GetSessionLayer()):
            if data is not None:
                scale = logic.water_scale_vector(data["level_pct"])
                if self._changed("water", scale):
                    self.stage.GetPrimAtPath(logic.PRIM_WATER).GetAttribute("xformOp:scale").Set(Gf.Vec3d(*scale))
                pump = logic.pump_material(bool(data["pump_on"]))
                if self._changed("pump", pump):
                    self._bind(logic.PRIM_PUMP, pump)
                self._apply_marker(data.get("predicted_level_pct"))
            light = logic.light_material(data, state)
            if self._changed("light", light):
                self._bind(logic.PRIM_ALARM_LIGHT, light)

    def _apply_marker(self, predicted):
        z = logic.prediction_marker_z(predicted)
        if not self._changed("marker", z):
            return
        prim = self.stage.GetPrimAtPath(logic.PRIM_PREDICTION_MARKER)
        if z is None:
            UsdGeom.Imageable(prim).MakeInvisible()
        else:
            UsdGeom.Imageable(prim).MakeVisible()
            prim.GetAttribute("xformOp:translate").Set(Gf.Vec3d(0.0, 0.0, z))