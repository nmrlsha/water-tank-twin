"""The UI panel (needs omni.ui, which Kit provides). Shows values, forecast, trend and alarms.

Only create and update this from Kit's update event / main thread, never from the MQTT thread.
"""
import omni.ui as ui
from omni.ui import color as cl

try:                                   # inside Kit this file is part of a package
    from . import twin_logic as logic
except ImportError:                    # on the laptop / pytest it is a plain module
    import twin_logic as logic

# (label shown on screen) -> filled from twin_logic.panel_rows(); the last four are extra rows
ROW_LABELS = ("Connection", "Water level", "Inflow", "Outflow", "Pump", "AI forecast",
              "Rule alarm", "AI warning", "Data time (UTC)")
EXTRA_LABELS = ("Trend", "Forecast change", "Data delay", "Rejected messages")


class TankPanel:
    def __init__(self):
        self._banner = ("Waiting for data", logic.GREY)
        self._values = {}
        self._window = ui.Window("Tank Twin", width=380, height=640)
        with self._window.frame:
            with ui.VStack(spacing=6):
                self._banner_frame = ui.Frame(height=56)
                self._banner_frame.set_build_fn(self._build_banner)
                for name in ROW_LABELS + EXTRA_LABELS:
                    with ui.HStack(height=22):
                        ui.Label(name, width=140)
                        self._values[name] = ui.Label("-")
                ui.Label("Water level, last 2 minutes (%)", height=20)
                self._plot = ui.Plot(ui.Type.LINE, 0.0, 100.0, 0.0, 0.0, height=90)

    def _build_banner(self):
        text, rgb = self._banner
        text_colour = cl(0.0, 0.0, 0.0) if rgb in (logic.GREEN, logic.AMBER) else cl(1.0, 1.0, 1.0)
        with ui.ZStack():
            ui.Rectangle(style={"background_color": cl(*rgb), "border_radius": 6})
            ui.Label(text, alignment=ui.Alignment.CENTER,
                     style={"color": text_colour, "font_size": 18})

    def update(self, state):
        """state is a TwinState. Cheap enough to call on every new message."""
        data, connection = state.data, state.connection()

        banner = logic.banner(data, connection)
        if banner != self._banner:                     # rebuild only when it really changes
            self._banner = banner
            self._banner_frame.rebuild()

        rows = dict(state.rows())
        for name in ROW_LABELS:
            self._values[name].text = rows.get(name, "-")

        self._values["Trend"].text = logic.trend_label(*state.trend())
        self._values["Forecast change"].text = logic.forecast_change_text(data)
        delay = state.delay_summary()
        self._values["Data delay"].text = f"{delay[0]:.2f} s (mean {delay[1]:.2f} s)" if delay else "-"
        self._values["Rejected messages"].text = str(state.rejected)

        levels = list(state.levels)
        if len(levels) >= 2:
            self._plot.set_data(*levels)

    def destroy(self):
        self._window.destroy()
        self._window = None