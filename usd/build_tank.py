"""Builds the water tank digital twin scene as OpenUSD (usd/tank.usda).

Run from the top-level folder:  python usd/build_tank.py
Units: metres. Up axis: Y. Tank capacity is about 100 L, matching tank_model.py.

Prim map (what the Kit extension controls):
  /World/Tank/Water                scale Y  <- level_pct / 100   (pivot at the tank floor)
  /World/Pump/Indicator            displayColor <- pump_on (green = ON, grey = off)
  /World/Tank/AlarmLight           displayColor <- alarm / ai_warning
  /World/Inlet/FlowMarker          displayColor <- inflow state (optional)
"""
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade, Vt

OUTPUT = Path("usd/tank.usda")

# ---- Dimensions (metres) -------------------------------------------------
TANK_RADIUS = 0.20
TANK_HEIGHT = 0.80                    # pi * 0.2^2 * 0.8 = 100.5 L, about the simulator's 100 L
WALL = 0.01
FLOOR_T = 0.02                        # base plate thickness
WATER_RADIUS = TANK_RADIUS - WALL
WATER_FULL_H = TANK_HEIGHT - FLOOR_T - 0.02   # water height at level_pct = 100
PIPE_R = 0.03
INLET_Y = 0.70
OUTLET_Y = 0.10

GREY = (0.55, 0.57, 0.60)
STEEL = (0.35, 0.38, 0.42)
BLUE = (0.10, 0.45, 0.90)


def xform(stage, path, translate=(0, 0, 0)):
    x = UsdGeom.Xform.Define(stage, path)
    x.AddTranslateOp().Set(Gf.Vec3d(*translate))
    return x


def cylinder(stage, path, radius, height, translate=(0, 0, 0), axis="Y", color=GREY):
    c = UsdGeom.Cylinder.Define(stage, path)
    c.CreateRadiusAttr(radius)
    c.CreateHeightAttr(height)
    c.CreateAxisAttr(axis)
    c.AddTranslateOp().Set(Gf.Vec3d(*translate))
    c.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    return c


def sphere(stage, path, radius, translate=(0, 0, 0), color=GREY):
    s = UsdGeom.Sphere.Define(stage, path)
    s.CreateRadiusAttr(radius)
    s.AddTranslateOp().Set(Gf.Vec3d(*translate))
    s.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    return s


def cube(stage, path, size, translate=(0, 0, 0), color=GREY):
    """A box of the given (x, y, z) size, centred on translate."""
    b = UsdGeom.Cube.Define(stage, path)
    b.CreateSizeAttr(1.0)
    b.AddTranslateOp().Set(Gf.Vec3d(*translate))
    b.AddScaleOp().Set(Gf.Vec3f(*size))
    b.CreateDisplayColorAttr(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    return b


def translucent_material(stage, path, color, opacity):
    mat = UsdShade.Material.Define(stage, path)
    shader = UsdShade.Shader.Define(stage, path + "/Shader")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(opacity)
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.15)
    mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return mat


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(OUTPUT))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    stage.SetTimeCodesPerSecond(24)

    world = UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())

    # ---- Materials -------------------------------------------------------
    UsdGeom.Scope.Define(stage, "/World/Looks")
    glass = translucent_material(stage, "/World/Looks/TankGlass", (0.80, 0.90, 1.00), 0.18)
    water_mat = translucent_material(stage, "/World/Looks/WaterMat", BLUE, 0.70)

    # ---- Floor -----------------------------------------------------------
    cube(stage, "/World/Floor", (2.4, 0.02, 1.6), translate=(0.2, -0.01, 0), color=(0.78, 0.79, 0.80))

    # ---- Tank ------------------------------------------------------------
    xform(stage, "/World/Tank")
    cylinder(stage, "/World/Tank/Base", TANK_RADIUS + 0.02, FLOOR_T,
             translate=(0, FLOOR_T / 2, 0), color=STEEL)
    shell = cylinder(stage, "/World/Tank/Shell", TANK_RADIUS, TANK_HEIGHT,
                     translate=(0, TANK_HEIGHT / 2, 0), color=(0.8, 0.9, 1.0))
    UsdShade.MaterialBindingAPI.Apply(shell.GetPrim()).Bind(glass)
    cylinder(stage, "/World/Tank/Lid", TANK_RADIUS + 0.01, 0.015,
             translate=(0, TANK_HEIGHT + 0.0075, 0), color=STEEL)

    # Water: an Xform whose ORIGIN IS ON THE TANK FLOOR. The cylinder inside is centred
    # half its height up, so scaling the Xform in Y makes the water grow upward.
    xform(stage, "/World/Tank/Water", translate=(0, FLOOR_T, 0))
    water_geom = cylinder(stage, "/World/Tank/Water/Geom", WATER_RADIUS, WATER_FULL_H,
                          translate=(0, WATER_FULL_H / 2, 0), color=BLUE)
    UsdShade.MaterialBindingAPI.Apply(water_geom.GetPrim()).Bind(water_mat)
    water = UsdGeom.Xformable(stage.GetPrimAtPath("/World/Tank/Water"))
    water_scale = water.AddScaleOp()
    water_scale.Set(Gf.Vec3f(1.0, 0.5, 1.0))          # starts at 50% level

    # Alarm light on top of the tank (the extension changes its displayColor)
    sphere(stage, "/World/Tank/AlarmLight", 0.035,
           translate=(0, TANK_HEIGHT + 0.06, 0), color=(0.1, 0.8, 0.2))

    # ---- Inlet pipe (left side, enters near the top) ----------------------
    xform(stage, "/World/Inlet")
    inlet_len = 0.55
    cylinder(stage, "/World/Inlet/Pipe", PIPE_R, inlet_len, axis="X",
             translate=(-(TANK_RADIUS + inlet_len / 2 - 0.03), INLET_Y, 0), color=STEEL)
    cylinder(stage, "/World/Inlet/Flange", PIPE_R + 0.012, 0.03, axis="X",
             translate=(-TANK_RADIUS - 0.005, INLET_Y, 0), color=GREY)
    sphere(stage, "/World/Inlet/FlowMarker", 0.022,
           translate=(-(TANK_RADIUS + inlet_len - 0.08), INLET_Y + PIPE_R + 0.03, 0),
           color=(0.2, 0.7, 0.9))

    # ---- Outlet pipe with pump (right side, near the bottom) ---------------
    xform(stage, "/World/Outlet")
    outlet_len = 0.70
    cylinder(stage, "/World/Outlet/Pipe", PIPE_R, outlet_len, axis="X",
             translate=(TANK_RADIUS + outlet_len / 2 - 0.03, OUTLET_Y, 0), color=STEEL)
    cylinder(stage, "/World/Outlet/Flange", PIPE_R + 0.012, 0.03, axis="X",
             translate=(TANK_RADIUS + 0.005, OUTLET_Y, 0), color=GREY)

    pump_x = TANK_RADIUS + 0.30
    xform(stage, "/World/Pump")
    cylinder(stage, "/World/Pump/Body", 0.065, 0.16, axis="X",
             translate=(pump_x, OUTLET_Y, 0), color=(0.20, 0.30, 0.60))
    cylinder(stage, "/World/Pump/Housing", 0.075, 0.07, axis="Y",
             translate=(pump_x, OUTLET_Y + 0.06, 0), color=(0.25, 0.35, 0.65))
    sphere(stage, "/World/Pump/Indicator", 0.025,
           translate=(pump_x, OUTLET_Y + 0.135, 0), color=(0.55, 0.55, 0.55))
    cube(stage, "/World/Pump/Stand", (0.20, 0.04, 0.14),
         translate=(pump_x, 0.02, 0), color=STEEL)

    # ---- Light and camera ---------------------------------------------------
    sun = UsdLux.DistantLight.Define(stage, "/World/Lights/Sun")
    sun.CreateIntensityAttr(2500)
    sun.AddRotateXYZOp().Set(Gf.Vec3f(-50, 35, 0))
    dome = UsdLux.DomeLight.Define(stage, "/World/Lights/Sky")
    dome.CreateIntensityAttr(600)

    cam = UsdGeom.Camera.Define(stage, "/World/Camera")
    cam.CreateFocalLengthAttr(28.0)
    cam.AddTranslateOp().Set(Gf.Vec3d(0.35, 0.75, 1.75))
    cam.AddRotateXYZOp().Set(Gf.Vec3f(-12, 0, 0))

    stage.GetRootLayer().Save()
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    build()