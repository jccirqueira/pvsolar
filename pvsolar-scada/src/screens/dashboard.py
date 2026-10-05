"""
Dashboard Screen.

Main SCADA dashboard with plant overview.
"""


from src.core.screens import Screen, ScreenManager, Widget, WidgetType


def create_dashboard_screen(screen_manager: ScreenManager) -> Screen:
    """Create the main dashboard screen."""
    screen = screen_manager.create_screen("dashboard", "Dashboard", "🏠")

    # Plant Overview Group
    screen.add_widget(Widget(
        widget_id="plant_status",
        widget_type=WidgetType.GROUP,
        label="Plant Overview",
        x=0, y=0, width=400, height=200,
    ))

    screen.add_widget(Widget(
        widget_id="plant_name",
        widget_type=WidgetType.LABEL,
        label="Plant Name",
        x=10, y=30, width=200, height=30,
        value="Solar Plant",
        font_size=16,
        bold=True,
    ))

    screen.add_widget(Widget(
        widget_id="plant_status_led",
        widget_type=WidgetType.LED,
        label="Status",
        x=10, y=70, width=80, height=30,
        value=True,
        color_on="#00FF00",
        color_off="#FF0000",
    ))

    screen.add_widget(Widget(
        widget_id="plant_status_text",
        widget_type=WidgetType.LABEL,
        label="Status",
        x=100, y=70, width=150, height=30,
        value="ONLINE",
        color="#00FF00",
    ))

    screen.add_widget(Widget(
        widget_id="plant_uptime",
        widget_type=WidgetType.LABEL,
        label="Uptime",
        x=10, y=110, width=200, height=30,
        value="0d 0h 0m",
    ))

    screen.add_widget(Widget(
        widget_id="plant_last_update",
        widget_type=WidgetType.LABEL,
        label="Last Update",
        x=10, y=140, width=200, height=30,
        value="--:--:--",
    ))

    # Power Production Group
    screen.add_widget(Widget(
        widget_id="power_group",
        widget_type=WidgetType.GROUP,
        label="Power Production",
        x=420, y=0, width=400, height=200,
    ))

    screen.add_widget(Widget(
        widget_id="current_power",
        widget_type=WidgetType.GAUGE,
        label="Current Power (kW)",
        x=430, y=30, width=180, height=120,
        value=0.0,
        min_val=0.0,
        max_val=100.0,
        unit="kW",
        decimals=2,
        color="#4CAF50",
    ))

    screen.add_widget(Widget(
        widget_id="daily_energy",
        widget_type=WidgetType.GAUGE,
        label="Daily Energy (kWh)",
        x=620, y=30, width=180, height=120,
        value=0.0,
        min_val=0.0,
        max_val=500.0,
        unit="kWh",
        decimals=1,
        color="#2196F3",
    ))

    screen.add_widget(Widget(
        widget_id="efficiency",
        widget_type=WidgetType.LABEL,
        label="Efficiency",
        x=430, y=160, width=180, height=30,
        value="0.0%",
    ))

    screen.add_widget(Widget(
        widget_id="capacity_factor",
        widget_type=WidgetType.LABEL,
        label="Capacity Factor",
        x=620, y=160, width=180, height=30,
        value="0.0%",
    ))

    # Weather Group
    screen.add_widget(Widget(
        widget_id="weather_group",
        widget_type=WidgetType.GROUP,
        label="Weather",
        x=0, y=220, width=400, height=150,
    ))

    screen.add_widget(Widget(
        widget_id="irradiance",
        widget_type=WidgetType.GAUGE,
        label="Irradiance (W/m²)",
        x=10, y=250, width=120, height=100,
        value=0.0,
        min_val=0.0,
        max_val=1200.0,
        unit="W/m²",
        decimals=0,
        color="#FF9800",
    ))

    screen.add_widget(Widget(
        widget_id="temperature",
        widget_type=WidgetType.THERMOMETER,
        label="Temperature (°C)",
        x=140, y=250, width=60, height=100,
        value=25.0,
        min_val=-10.0,
        max_val=60.0,
        unit="°C",
        decimals=1,
    ))

    screen.add_widget(Widget(
        widget_id="wind_speed",
        widget_type=WidgetType.LABEL,
        label="Wind",
        x=220, y=250, width=80, height=30,
        value="0.0 m/s",
    ))

    screen.add_widget(Widget(
        widget_id="humidity",
        widget_type=WidgetType.LABEL,
        label="Humidity",
        x=220, y=280, width=80, height=30,
        value="0.0%",
    ))

    screen.add_widget(Widget(
        widget_id="weather_condition",
        widget_type=WidgetType.LABEL,
        label="Condition",
        x=310, y=250, width=80, height=30,
        value="--",
    ))

    # Inverter Status Group
    screen.add_widget(Widget(
        widget_id="inverter_group",
        widget_type=WidgetType.GROUP,
        label="Inverter Status",
        x=420, y=220, width=400, height=150,
    ))

    screen.add_widget(Widget(
        widget_id="inverter_count",
        widget_type=WidgetType.LABEL,
        label="Active/Total",
        x=430, y=250, width=120, height=30,
        value="0/0",
    ))

    screen.add_widget(Widget(
        widget_id="inverter_total_power",
        widget_type=WidgetType.LABEL,
        label="Total Power",
        x=430, y=280, width=120, height=30,
        value="0.0 kW",
    ))

    screen.add_widget(Widget(
        widget_id="inverter_avg_efficiency",
        widget_type=WidgetType.LABEL,
        label="Avg Efficiency",
        x=430, y=310, width=120, height=30,
        value="0.0%",
    ))

    screen.add_widget(Widget(
        widget_id="inverter_alarm_count",
        widget_type=WidgetType.LABEL,
        label="Alarms",
        x=560, y=250, width=80, height=30,
        value="0",
        color="#FF0000",
    ))

    # Production Chart
    screen.add_widget(Widget(
        widget_id="production_chart",
        widget_type=WidgetType.CHART,
        label="Today's Production",
        x=0, y=390, width=820, height=200,
        chart_type="line",
        series=["power", "irradiance"],
        time_range="24h",
    ))

    return screen
