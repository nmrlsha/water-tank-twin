"""Checks usd/tank.usda: structure, units, and that the water grows upward from the floor.

Run from the top-level folder:  python usd/check_tank.py
Exit code 0 = all checks passed.
"""
import sys

from pxr import Gf, Usd, UsdGeom

PATH = "usd/tank.usda"
REQUIRED_PRIMS = [
    "/World", "/World/Tank", "/World/Tank/Shell", "/World/Tank/Water", "/World/Tank/Water/Geom",
    "/World/Tank/AlarmLight", "/World/Inlet/Pipe", "/World/Outlet/Pipe",
    "/World/Pump/Body", "/World/Pump/Indicator", "/World/Camera",
]
failures = []


def check(condition, message):
    print(("PASS  " if condition else "FAIL  ") + message)
    if not condition:
        failures.append(message)


stage = Usd.Stage.Open(PATH)
check(UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y, "up axis is Y")
check(UsdGeom.GetStageMetersPerUnit(stage) == 1.0, "units are metres")
check(stage.GetDefaultPrim().GetPath() == "/World", "default prim is /World")

for p in REQUIRED_PRIMS:
    check(stage.GetPrimAtPath(p).IsValid(), f"prim exists: {p}")

# The water must grow UPWARD from the tank floor: its lowest point must not move with scale.
cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
water = UsdGeom.Xformable(stage.GetPrimAtPath("/World/Tank/Water"))
scale_op = [op for op in water.GetOrderedXformOps() if op.GetOpType() == UsdGeom.XformOp.TypeScale][0]
bottoms, heights = [], []
for s in (0.1, 0.5, 1.0):
    scale_op.Set(Gf.Vec3f(1.0, s, 1.0))
    box = cache.ComputeWorldBound(stage.GetPrimAtPath("/World/Tank/Water")).ComputeAlignedRange()
    bottoms.append(box.GetMin()[1])
    heights.append(box.GetMax()[1] - box.GetMin()[1])
    cache.Clear()
check(max(bottoms) - min(bottoms) < 1e-6, f"water bottom stays on the floor (y = {bottoms[0]:.3f} m)")
check(heights[0] < heights[1] < heights[2], f"water height grows with scale: {[round(h, 3) for h in heights]} m")

shell = cache.ComputeWorldBound(stage.GetPrimAtPath("/World/Tank/Shell")).ComputeAlignedRange()
check(heights[2] < shell.GetMax()[1] - shell.GetMin()[1], "full water stays below the tank top")

print()
print("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED")
sys.exit(1 if failures else 0)