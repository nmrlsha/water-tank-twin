"""Physics model of one water tank with an inlet pipe and a pump on the outlet.

No networking here, so it can be unit tested and reused to generate training data.
"""
import math
import random

TANK_CAPACITY_L = 100.0      # small, scaled tank so level changes are visible within minutes
PUMP_RATE_LPM = 20.0         # outflow while the pump runs
PUMP_ON_ABOVE_PCT = 70.0     # controller starts the pump above this level
PUMP_OFF_BELOW_PCT = 30.0    # controller stops the pump below this level
NOMINAL_INFLOW_LPM = 8.0
ABNORMAL_INFLOW_LPM = 40.0

# normal          : healthy operation, level cycles between about 30% and 70%
# abnormal_inflow : inlet suddenly delivers far too much water -> overflow risk
# pump_failure    : pump stuck OFF -> level keeps rising -> overflow risk
# pump_stuck_on   : pump stuck ON -> level keeps falling -> low level
SCENARIOS = ("normal", "abnormal_inflow", "pump_failure", "pump_stuck_on")


def _clamp(value, low, high):
    return max(low, min(high, value))


class TankSimulator:
    def __init__(self, seed=None, level_pct=50.0):
        self.rng = random.Random(seed)   # same seed = same noise = reproducible runs
        self.level_pct = level_pct       # true level (the reported one adds sensor noise)
        self.pump_on = False
        self.scenario = "normal"
        self.t = 0.0                     # simulated seconds elapsed

    def set_scenario(self, name):
        if name not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {name}")
        self.scenario = name

    def step(self, dt=1.0):
        """Advance the tank by dt seconds and return the sensor readings."""
        self.t += dt

        # 1. Inlet flow
        if self.scenario == "abnormal_inflow":
            inflow = ABNORMAL_INFLOW_LPM + self.rng.gauss(0, 1.0)
        else:
            inflow = (NOMINAL_INFLOW_LPM
                      + 2.0 * math.sin(2 * math.pi * self.t / 300.0)   # slow daily-demand-like swing
                      + self.rng.gauss(0, 0.3))                         # sensor noise

        # 2. Pump controller (hysteresis: on above 70%, off below 30%)
        if self.scenario == "pump_failure":
            self.pump_on = False
        elif self.scenario == "pump_stuck_on":
            self.pump_on = True
        elif self.level_pct > PUMP_ON_ABOVE_PCT:
            self.pump_on = True
        elif self.level_pct < PUMP_OFF_BELOW_PCT:
            self.pump_on = False

        # 3. Outlet flow
        outflow = PUMP_RATE_LPM + self.rng.gauss(0, 0.4) if self.pump_on else 0.0

        inflow = _clamp(inflow, 0.0, 50.0)
        outflow = _clamp(outflow, 0.0, 50.0)

        # 4. Mass balance: litres in minus litres out, converted to % of tank height
        litres_change = (inflow - outflow) * dt / 60.0
        self.level_pct = _clamp(self.level_pct + litres_change / TANK_CAPACITY_L * 100.0, 0.0, 100.0)

        # 5. What the level sensor reports (true level plus a little noise)
        measured = _clamp(self.level_pct + self.rng.gauss(0, 0.15), 0.0, 100.0)

        return {
            "level_pct": round(measured, 2),
            "inflow_lpm": round(inflow, 2),
            "outflow_lpm": round(outflow, 2),
            "pump_on": self.pump_on,
        }


if __name__ == "__main__":
    # Quick demo: python simulator/tank_model.py abnormal_inflow
    import sys
    scenario = sys.argv[1] if len(sys.argv) > 1 else "normal"
    sim = TankSimulator(seed=1)
    sim.set_scenario(scenario)
    print(f"Scenario: {scenario}")
    for second in range(0, 601):
        s = sim.step()
        if second % 10 == 0:
            print(f"t={second:4d}s  level={s['level_pct']:6.2f}%  in={s['inflow_lpm']:5.2f}  "
                  f"out={s['outflow_lpm']:5.2f}  pump={'ON' if s['pump_on'] else 'off'}")