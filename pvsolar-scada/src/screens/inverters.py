"""
Inverter Screen.

Detailed monitoring of solar inverters.
"""


from src.core.screens import Screen, ScreenManager, Widget, WidgetType


def create_inverter_screen(screen_manager: ScreenManager, num_inverters: int = 6) -> Screen:
    """Create the inverter monitoring screen."""
    screen = screen_manager.create_screen("inverters", "Inverters", "⚡")

    # Inverter selector
    screen.add_widget(Widget(
        widget_id="inverter_selector",
        widget_type=WidgetType.COMBOBOX,
        label="Select Inverter",
        x=10, y=10, width=200, height=30,
        options=[f"Inverter {i+1}" for i in range(num_inverters)],
        selected_index=0,
    ))

    # Inverter Overview Grid
    for i in range(min(num_inverters, 6)):
        row = i // 3
        col = i % 3
        x_offset = col * 280
        y_offset = 50 + row * 180

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_group",
            widget_type=WidgetType.GROUP,
            label=f"Inverter {i+1}",
            x=x_offset, y=y_offset, width=270, height=170,
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_status",
            widget_type=WidgetType.LED,
            label="Status",
            x=x_offset+10, y=y_offset+30, width=60, height=25,
            value=True,
            color_on="#00FF00",
            color_off="#FF0000",
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_power",
            widget_type=WidgetType.LABEL,
            label="Power",
            x=x_offset+80, y=y_offset+30, width=80, height=25,
            value="0.0 kW",
            font_size=14,
            bold=True,
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_energy",
            widget_type=WidgetType.LABEL,
            label="Energy",
            x=x_offset+170, y=y_offset+30, width=80, height=25,
            value="0.0 kWh",
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_efficiency",
            widget_type=WidgetType.LABEL,
            label="Efficiency",
            x=x_offset+10, y=y_offset+60, width=100, height=25,
            value="0.0%",
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_temperature",
            widget_type=WidgetType.LABEL,
            label="Temp",
            x=x_offset+120, y=y_offset+60, width=80, height=25,
            value="0.0°C",
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_grid_voltage",
            widget_type=WidgetType.LABEL,
            label="V Grid",
            x=x_offset+10, y=y_offset+90, width=80, height=25,
            value="0.0 V",
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_grid_frequency",
            widget_type=WidgetType.LABEL,
            label="f Grid",
            x=x_offset+100, y=y_offset+90, width=80, height=25,
            value="0.0 Hz",
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_dc_voltage",
            widget_type=WidgetType.LABEL,
            label="V DC",
            x=x_offset+10, y=y_offset+120, width=80, height=25,
            value="0.0 V",
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_dc_current",
            widget_type=WidgetType.LABEL,
            label="I DC",
            x=x_offset+100, y=y_offset+120, width=80, height=25,
            value="0.0 A",
        ))

        screen.add_widget(Widget(
            widget_id=f"inverter_{i+1}_alarms",
            widget_type=WidgetType.LABEL,
            label="Alarms",
            x=x_offset+190, y=y_offset+120, width=70, height=25,
            value="0",
            color="#FF0000",
        ))

    # Detailed View (selected inverter)
    detail_x = 0
    detail_y = 420

    screen.add_widget(Widget(
        widget_id="detail_group",
        widget_type=WidgetType.GROUP,
        label="Detailed View",
        x=detail_x, y=detail_y, width=820, height=160,
    ))

    screen.add_widget(Widget(
        widget_id="detail_chart",
        widget_type=WidgetType.CHART,
        label="Power & Efficiency Trend",
        x=detail_x+10, y=detail_y+25, width=500, height=130,
        chart_type="line",
        series=["power", "efficiency"],
        time_range="24h",
    ))

    screen.add_widget(Widget(
        widget_id="detail_status_table",
        widget_type=WidgetType.TABLE,
        label="Status Parameters",
        x=detail_x+520, y=detail_y+25, width=290, height=130,
        columns=["Parameter", "Value", "Unit"],
        rows=[
            ["DC Voltage", "0.0", "V"],
            ["DC Current", "0.0", "A"],
            ["AC Voltage", "0.0", "V"],
            ["AC Current", "0.0", "A"],
            ["Frequency", "0.0", "Hz"],
            ["Power Factor", "0.00", ""],
        ],
    ))

    return screen
