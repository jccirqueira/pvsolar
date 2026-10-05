"""
Alarms Screen.

Alarm monitoring and management.
"""

from src.core.screens import Screen, ScreenManager, Widget, WidgetType


def create_alarms_screen(screen_manager: ScreenManager) -> Screen:
    """Create the alarms monitoring screen."""
    screen = screen_manager.create_screen("alarms", "Alarms", "🔔")

    # Alarm Summary Group
    screen.add_widget(Widget(
        widget_id="alarm_summary_group",
        widget_type=WidgetType.GROUP,
        label="Alarm Summary",
        x=0, y=0, width=820, height=80,
    ))

    screen.add_widget(Widget(
        widget_id="critical_count",
        widget_type=WidgetType.LABEL,
        label="Critical",
        x=10, y=30, width=100, height=30,
        value="0",
        color="#FF0000",
        font_size=18,
        bold=True,
    ))

    screen.add_widget(Widget(
        widget_id="warning_count",
        widget_type=WidgetType.LABEL,
        label="Warning",
        x=120, y=30, width=100, height=30,
        value="0",
        color="#FFA500",
        font_size=18,
        bold=True,
    ))

    screen.add_widget(Widget(
        widget_id="info_count",
        widget_type=WidgetType.LABEL,
        label="Info",
        x=230, y=30, width=100, height=30,
        value="0",
        color="#0000FF",
        font_size=18,
        bold=True,
    ))

    screen.add_widget(Widget(
        widget_id="acknowledged_count",
        widget_type=WidgetType.LABEL,
        label="Acknowledged",
        x=340, y=30, width=120, height=30,
        value="0",
        color="#00FF00",
        font_size=18,
        bold=True,
    ))

    screen.add_widget(Widget(
        widget_id="unacknowledged_count",
        widget_type=WidgetType.LABEL,
        label="Unacknowledged",
        x=470, y=30, width=140, height=30,
        value="0",
        color="#FF6600",
        font_size=18,
        bold=True,
    ))

    screen.add_widget(Widget(
        widget_id="total_alarms",
        widget_type=WidgetType.LABEL,
        label="Total",
        x=620, y=30, width=80, height=30,
        value="0",
        font_size=18,
        bold=True,
    ))

    # Alarm Controls
    screen.add_widget(Widget(
        widget_id="ack_all_button",
        widget_type=WidgetType.BUTTON,
        label="Acknowledge All",
        x=720, y=25, width=90, height=35,
        color="#4CAF50",
    ))

    screen.add_widget(Widget(
        widget_id="filter_combo",
        widget_type=WidgetType.COMBOBOX,
        label="Filter",
        x=10, y=90, width=150, height=30,
        options=["All", "Critical", "Warning", "Info", "Unacknowledged"],
        selected_index=0,
    ))

    screen.add_widget(Widget(
        widget_id="search_input",
        widget_type=WidgetType.LINEEDIT,
        label="Search",
        x=170, y=90, width=200, height=30,
        placeholder="Search alarms...",
    ))

    # Active Alarms Table
    screen.add_widget(Widget(
        widget_id="alarms_table",
        widget_type=WidgetType.TABLE,
        label="Active Alarms",
        x=0, y=130, width=820, height=300,
        columns=["Time", "Level", "Source", "Message", "Status"],
        rows=[],
        sortable=True,
        selectable=True,
        row_height=25,
    ))

    # Alarm Details Group
    screen.add_widget(Widget(
        widget_id="alarm_details_group",
        widget_type=WidgetType.GROUP,
        label="Alarm Details",
        x=0, y=440, width=400, height=140,
    ))

    screen.add_widget(Widget(
        widget_id="alarm_detail_id",
        widget_type=WidgetType.LABEL,
        label="Alarm ID",
        x=10, y=470, width=180, height=25,
        value="--",
    ))

    screen.add_widget(Widget(
        widget_id="alarm_detail_level",
        widget_type=WidgetType.LABEL,
        label="Level",
        x=10, y=500, width=100, height=25,
        value="--",
    ))

    screen.add_widget(Widget(
        widget_id="alarm_detail_source",
        widget_type=WidgetType.LABEL,
        label="Source",
        x=120, y=500, width=150, height=25,
        value="--",
    ))

    screen.add_widget(Widget(
        widget_id="alarm_detail_time",
        widget_type=WidgetType.LABEL,
        label="Time",
        x=10, y=530, width=180, height=25,
        value="--",
    ))

    screen.add_widget(Widget(
        widget_id="alarm_ack_button",
        widget_type=WidgetType.BUTTON,
        label="Acknowledge",
        x=10, y=560, width=100, height=30,
        color="#FF9800",
    ))

    # Alarm History
    screen.add_widget(Widget(
        widget_id="alarm_history_group",
        widget_type=WidgetType.GROUP,
        label="Alarm History (Last 24h)",
        x=420, y=440, width=400, height=140,
    ))

    screen.add_widget(Widget(
        widget_id="alarm_history_chart",
        widget_type=WidgetType.CHART,
        label="Alarms per Hour",
        x=430, y=470, width=380, height=100,
        chart_type="bar",
        series=["critical", "warning", "info"],
        time_range="24h",
    ))

    return screen
