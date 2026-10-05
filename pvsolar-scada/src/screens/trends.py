"""
Trends Screen.

Historical data visualization and trend analysis.
"""

from src.core.screens import Screen, ScreenManager, Widget, WidgetType


def create_trends_screen(screen_manager: ScreenManager) -> Screen:
    """Create the trends/screening screen."""
    screen = screen_manager.create_screen("trends", "Trends", "📈")
    
    # Trend Controls
    screen.add_widget(Widget(
        widget_id="trend_controls_group",
        widget_type=WidgetType.GROUP,
        label="Trend Controls",
        x=0, y=0, width=820, height=60,
    ))
    
    screen.add_widget(Widget(
        widget_id="time_range_combo",
        widget_type=WidgetType.COMBOBOX,
        label="Time Range",
        x=10, y=25, width=120, height=30,
        options=["1h", "6h", "24h", "7d", "30d"],
        selected_index=2,
    ))
    
    screen.add_widget(Widget(
        widget_id="refresh_rate_combo",
        widget_type=WidgetType.COMBOBOX,
        label="Refresh Rate",
        x=140, y=25, width=100, height=30,
        options=["1s", "5s", "10s", "30s", "1m"],
        selected_index=1,
    ))
    
    screen.add_widget(Widget(
        widget_id="trend_pause_button",
        widget_type=WidgetType.BUTTON,
        label="Pause",
        x=250, y=25, width=70, height=30,
        color="#FF9800",
    ))
    
    screen.add_widget(Widget(
        widget_id="trend_export_button",
        widget_type=WidgetType.BUTTON,
        label="Export CSV",
        x=330, y=25, width=80, height=30,
        color="#2196F3",
    ))
    
    screen.add_widget(Widget(
        widget_id="trend_screenshot_button",
        widget_type=WidgetType.BUTTON,
        label="Screenshot",
        x=420, y=25, width=90, height=30,
        color="#9C27B0",
    ))
    
    # Main Power Trend
    screen.add_widget(Widget(
        widget_id="power_trend_group",
        widget_type=WidgetType.GROUP,
        label="Power Production Trend",
        x=0, y=70, width=820, height=200,
    ))
    
    screen.add_widget(Widget(
        widget_id="power_trend_chart",
        widget_type=WidgetType.CHART,
        label="Power Output (kW)",
        x=10, y=100, width=800, height=160,
        chart_type="area",
        series=["actual_power", "forecast_power", "capacity"],
        time_range="24h",
        show_legend=True,
        show_grid=True,
    ))
    
    # Multi-parameter Trend
    screen.add_widget(Widget(
        widget_id="multi_trend_group",
        widget_type=WidgetType.GROUP,
        label="Multi-parameter Trend",
        x=0, y=280, width=820, height=200,
    ))
    
    screen.add_widget(Widget(
        widget_id="multi_trend_chart",
        widget_type=WidgetType.CHART,
        label="Select parameters to display",
        x=10, y=310, width=800, height=160,
        chart_type="multi_line",
        series=["power", "irradiance", "temperature", "efficiency"],
        time_range="24h",
        show_legend=True,
        show_grid=True,
    ))
    
    # Parameter Selection
    screen.add_widget(Widget(
        widget_id="param_check_power",
        widget_type=WidgetType.CHECKBOX,
        label="Power",
        x=10, y=490, width=80, height=25,
        checked=True,
        color="#4CAF50",
    ))
    
    screen.add_widget(Widget(
        widget_id="param_check_irradiance",
        widget_type=WidgetType.CHECKBOX,
        label="Irradiance",
        x=100, y=490, width=100, height=25,
        checked=True,
        color="#FF9800",
    ))
    
    screen.add_widget(Widget(
        widget_id="param_check_temperature",
        widget_type=WidgetType.CHECKBOX,
        label="Temperature",
        x=210, y=490, width=110, height=25,
        checked=True,
        color="#F44336",
    ))
    
    screen.add_widget(Widget(
        widget_id="param_check_efficiency",
        widget_type=WidgetType.CHECKBOX,
        label="Efficiency",
        x=330, y=490, width=100, height=25,
        checked=True,
        color="#2196F3",
    ))
    
    screen.add_widget(Widget(
        widget_id="param_check_voltage",
        widget_type=WidgetType.CHECKBOX,
        label="Voltage",
        x=440, y=490, width=80, height=25,
        checked=False,
        color="#9C27B0",
    ))
    
    screen.add_widget(Widget(
        widget_id="param_check_current",
        widget_type=WidgetType.CHECKBOX,
        label="Current",
        x=530, y=490, width=80, height=25,
        checked=False,
        color="#00BCD4",
    ))
    
    # Statistics Summary
    screen.add_widget(Widget(
        widget_id="stats_group",
        widget_type=WidgetType.GROUP,
        label="Statistics Summary",
        x=0, y=520, width=820, height=60,
    ))
    
    screen.add_widget(Widget(
        widget_id="stat_min",
        widget_type=WidgetType.LABEL,
        label="Min",
        x=10, y=545, width=100, height=25,
        value="0.0 kW",
    ))
    
    screen.add_widget(Widget(
        widget_id="stat_max",
        widget_type=WidgetType.LABEL,
        label="Max",
        x=120, y=545, width=100, height=25,
        value="0.0 kW",
    ))
    
    screen.add_widget(Widget(
        widget_id="stat_avg",
        widget_type=WidgetType.LABEL,
        label="Average",
        x=230, y=545, width=100, height=25,
        value="0.0 kW",
    ))
    
    screen.add_widget(Widget(
        widget_id="stat_total",
        widget_type=WidgetType.LABEL,
        label="Total Energy",
        x=340, y=545, width=120, height=25,
        value="0.0 kWh",
    ))
    
    screen.add_widget(Widget(
        widget_id="stat_stddev",
        widget_type=WidgetType.LABEL,
        label="Std Dev",
        x=470, y=545, width=100, height=25,
        value="0.0 kW",
    ))
    
    screen.add_widget(Widget(
        widget_id="stat_cpf",
        widget_type=WidgetType.LABEL,
        label="Capacity Factor",
        x=580, y=545, width=120, height=25,
        value="0.0%",
    ))
    
    return screen
