"""
Performance Screen.

Performance scoring and benchmarking.
"""

from src.core.screens import Screen, ScreenManager, Widget, WidgetType


def create_performance_screen(screen_manager: ScreenManager) -> Screen:
    """Create the performance monitoring screen."""
    screen = screen_manager.create_screen("performance", "Performance", "📊")
    
    # Performance Score Group
    screen.add_widget(Widget(
        widget_id="score_group",
        widget_type=WidgetType.GROUP,
        label="Performance Score",
        x=0, y=0, width=400, height=200,
    ))
    
    screen.add_widget(Widget(
        widget_id="overall_score",
        widget_type=WidgetType.GAUGE,
        label="Overall Score",
        x=10, y=30, width=180, height=150,
        value=0.0,
        min_val=0.0,
        max_val=100.0,
        unit="%",
        decimals=1,
        color="#4CAF50",
        ranges=[
            {"min": 0, "max": 40, "color": "#FF0000"},
            {"min": 40, "max": 60, "color": "#FFA500"},
            {"min": 60, "max": 80, "color": "#FFEB3B"},
            {"min": 80, "max": 100, "color": "#4CAF50"},
        ],
    ))
    
    screen.add_widget(Widget(
        widget_id="performance_grade",
        widget_type=WidgetType.LABEL,
        label="Grade",
        x=200, y=30, width=100, height=40,
        value="--",
        font_size=36,
        bold=True,
        color="#4CAF50",
    ))
    
    screen.add_widget(Widget(
        widget_id="performance_rank",
        widget_type=WidgetType.LABEL,
        label="Fleet Rank",
        x=200, y=80, width=100, height=30,
        value="--",
    ))
    
    screen.add_widget(Widget(
        widget_id="performance_percentile",
        widget_type=WidgetType.LABEL,
        label="Percentile",
        x=200, y=110, width=120, height=30,
        value="--",
    ))
    
    screen.add_widget(Widget(
        widget_id="performance_trend",
        widget_type=WidgetType.LABEL,
        label="Trend",
        x=200, y=140, width=100, height=30,
        value="--",
    ))
    
    # Performance Components Group
    screen.add_widget(Widget(
        widget_id="components_group",
        widget_type=WidgetType.GROUP,
        label="Performance Components",
        x=420, y=0, width=400, height=200,
    ))
    
    screen.add_widget(Widget(
        widget_id="pr_score",
        widget_type=WidgetType.PROGRESS,
        label="Performance Ratio (PR)",
        x=430, y=30, width=380, height=30,
        value=0.0,
        min_val=0.0,
        max_val=100.0,
        color="#4CAF50",
    ))
    
    screen.add_widget(Widget(
        widget_id="cef_score",
        widget_type=WidgetType.PROGRESS,
        label="Cleanliness Factor (CEF)",
        x=430, y=70, width=380, height=30,
        value=0.0,
        min_val=0.0,
        max_val=100.0,
        color="#2196F3",
    ))
    
    screen.add_widget(Widget(
        widget_id="availability_score",
        widget_type=WidgetType.PROGRESS,
        label="Availability",
        x=430, y=110, width=380, height=30,
        value=0.0,
        min_val=0.0,
        max_val=100.0,
        color="#FF9800",
    ))
    
    screen.add_widget(Widget(
        widget_id="efficiency_score",
        widget_type=WidgetType.PROGRESS,
        label="Efficiency",
        x=430, y=150, width=380, height=30,
        value=0.0,
        min_val=0.0,
        max_val=100.0,
        color="#9C27B0",
    ))
    
    # Performance Trends Group
    screen.add_widget(Widget(
        widget_id="perf_trend_group",
        widget_type=WidgetType.GROUP,
        label="Performance Trends",
        x=0, y=220, width=820, height=200,
    ))
    
    screen.add_widget(Widget(
        widget_id="perf_trend_chart",
        widget_type=WidgetType.CHART,
        label="Performance Score History",
        x=10, y=250, width=800, height=160,
        chart_type="line",
        series=["overall", "pr", "cef", "availability", "efficiency"],
        time_range="30d",
        show_legend=True,
    ))
    
    # Benchmark Group
    screen.add_widget(Widget(
        widget_id="benchmark_group",
        widget_type=WidgetType.GROUP,
        label="Benchmark Comparison",
        x=0, y=440, width=400, height=140,
    ))
    
    screen.add_widget(Widget(
        widget_id="vs_fleet_avg",
        widget_type=WidgetType.LABEL,
        label="vs Fleet Average",
        x=10, y=470, width=180, height=30,
        value="--",
    ))
    
    screen.add_widget(Widget(
        widget_id="vs_peer_avg",
        widget_type=WidgetType.LABEL,
        label="vs Peer Average",
        x=10, y=500, width=180, height=30,
        value="--",
    ))
    
    screen.add_widget(Widget(
        widget_id="vs_historical",
        widget_type=WidgetType.LABEL,
        label="vs Historical",
        x=10, y=530, width=180, height=30,
        value="--",
    ))
    
    screen.add_widget(Widget(
        widget_id="vs_best",
        widget_type=WidgetType.LABEL,
        label="vs Best Performer",
        x=10, y=560, width=180, height=30,
        value="--",
    ))
    
    screen.add_widget(Widget(
        widget_id="benchmark_chart",
        widget_type=WidgetType.CHART,
        label="Benchmark",
        x=200, y=470, width=200, height=100,
        chart_type="radar",
        series=["pr", "cef", "availability", "efficiency"],
    ))
    
    # Insights Group
    screen.add_widget(Widget(
        widget_id="insights_group",
        widget_type=WidgetType.GROUP,
        label="Insights & Recommendations",
        x=420, y=440, width=400, height=140,
    ))
    
    screen.add_widget(Widget(
        widget_id="insights_table",
        widget_type=WidgetType.TABLE,
        label="Recommendations",
        x=430, y=470, width=380, height=100,
        columns=["Priority", "Recommendation"],
        rows=[
            ["--", "No recommendations available"],
        ],
    ))
    
    return screen
