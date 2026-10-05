"""
Weather Screen.

Weather station monitoring and solar resource data.
"""

from src.core.screens import Screen, ScreenManager, Widget, WidgetType


def create_weather_screen(screen_manager: ScreenManager) -> Screen:
    """Create the weather monitoring screen."""
    screen = screen_manager.create_screen("weather", "Weather", "🌤️")

    # Solar Resource Group
    screen.add_widget(Widget(
        widget_id="solar_group",
        widget_type=WidgetType.GROUP,
        label="Solar Resource",
        x=0, y=0, width=400, height=200,
    ))

    screen.add_widget(Widget(
        widget_id="irradiance_gauge",
        widget_type=WidgetType.GAUGE,
        label="Global Irradiance (W/m²)",
        x=10, y=30, width=180, height=150,
        value=0.0,
        min_val=0.0,
        max_val=1200.0,
        unit="W/m²",
        decimals=0,
        color="#FF9800",
    ))

    screen.add_widget(Widget(
        widget_id="diffuse_irradiance",
        widget_type=WidgetType.LABEL,
        label="Diffuse",
        x=200, y=30, width=100, height=30,
        value="0 W/m²",
    ))

    screen.add_widget(Widget(
        widget_id="direct_irradiance",
        widget_type=WidgetType.LABEL,
        label="Direct",
        x=200, y=60, width=100, height=30,
        value="0 W/m²",
    ))

    screen.add_widget(Widget(
        widget_id="reflected_irradiance",
        widget_type=WidgetType.LABEL,
        label="Reflected",
        x=200, y=90, width=100, height=30,
        value="0 W/m²",
    ))

    screen.add_widget(Widget(
        widget_id="peak_sun_hours",
        widget_type=WidgetType.LABEL,
        label="Peak Sun Hours",
        x=200, y=120, width=120, height=30,
        value="0.0 h",
    ))

    screen.add_widget(Widget(
        widget_id="solar_angle",
        widget_type=WidgetType.LABEL,
        label="Solar Angle",
        x=200, y=150, width=120, height=30,
        value="0.0°",
    ))

    # Ambient Conditions Group
    screen.add_widget(Widget(
        widget_id="ambient_group",
        widget_type=WidgetType.GROUP,
        label="Ambient Conditions",
        x=420, y=0, width=400, height=200,
    ))

    screen.add_widget(Widget(
        widget_id="ambient_temp",
        widget_type=WidgetType.THERMOMETER,
        label="Temperature",
        x=430, y=30, width=60, height=150,
        value=25.0,
        min_val=-10.0,
        max_val=60.0,
        unit="°C",
        decimals=1,
    ))

    screen.add_widget(Widget(
        widget_id="humidity",
        widget_type=WidgetType.GAUGE,
        label="Humidity (%)",
        x=500, y=30, width=100, height=100,
        value=50.0,
        min_val=0.0,
        max_val=100.0,
        unit="%",
        decimals=0,
        color="#2196F3",
    ))

    screen.add_widget(Widget(
        widget_id="wind_speed",
        widget_type=WidgetType.GAUGE,
        label="Wind Speed (m/s)",
        x=610, y=30, width=100, height=100,
        value=0.0,
        min_val=0.0,
        max_val=30.0,
        unit="m/s",
        decimals=1,
        color="#9C27B0",
    ))

    screen.add_widget(Widget(
        widget_id="wind_direction",
        widget_type=WidgetType.COMPASS,
        label="Wind Direction",
        x=720, y=30, width=80, height=80,
        value=0.0,
        min_val=0.0,
        max_val=360.0,
        unit="°",
    ))

    screen.add_widget(Widget(
        widget_id="pressure",
        widget_type=WidgetType.LABEL,
        label="Pressure",
        x=500, y=140, width=100, height=30,
        value="0 hPa",
    ))

    screen.add_widget(Widget(
        widget_id="rainfall",
        widget_type=WidgetType.LABEL,
        label="Rainfall",
        x=610, y=140, width=100, height=30,
        value="0.0 mm",
    ))

    screen.add_widget(Widget(
        widget_id="weather_condition",
        widget_type=WidgetType.LABEL,
        label="Condition",
        x=720, y=140, width=80, height=30,
        value="--",
    ))

    # Module Temperature Group
    screen.add_widget(Widget(
        widget_id="module_group",
        widget_type=WidgetType.GROUP,
        label="Module Temperature",
        x=0, y=220, width=820, height=120,
    ))

    screen.add_widget(Widget(
        widget_id="module_temp_chart",
        widget_type=WidgetType.CHART,
        label="Module Temperature Trend",
        x=10, y=250, width=800, height=80,
        chart_type="line",
        series=["module_temp", "ambient_temp"],
        time_range="24h",
    ))

    # Solar Production vs Irradiance
    screen.add_widget(Widget(
        widget_id="production_group",
        widget_type=WidgetType.GROUP,
        label="Production vs Irradiance",
        x=0, y=360, width=820, height=200,
    ))

    screen.add_widget(Widget(
        widget_id="production_irradiance_chart",
        widget_type=WidgetType.CHART,
        label="Power Output vs Solar Irradiance",
        x=10, y=390, width=800, height=160,
        chart_type="dual_axis",
        series=["power", "irradiance"],
        time_range="24h",
    ))

    return screen
