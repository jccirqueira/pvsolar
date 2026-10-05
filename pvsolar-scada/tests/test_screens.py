"""
Tests for pvSolar SCADA Screen Manager.
"""

from src.core.screens import Screen, ScreenManager, Widget, WidgetType


class TestWidget:
    """Tests for Widget class."""

    def test_create_widget(self):
        widget = Widget(
            widget_id="test_widget",
            widget_type=WidgetType.LABEL,
            label="Test Label",
            x=10,
            y=20,
            width=100,
            height=30,
        )
        assert widget.widget_id == "test_widget"
        assert widget.widget_type == WidgetType.LABEL
        assert widget.label == "Test Label"
        assert widget.x == 10
        assert widget.y == 20
        assert widget.width == 100
        assert widget.height == 30
        assert widget.visible is True
        assert widget.enabled is True

    def test_widget_to_dict(self):
        widget = Widget(
            widget_id="test_widget",
            widget_type=WidgetType.GAUGE,
            label="Test Gauge",
            value=50.0,
        )
        data = widget.to_dict()
        assert data["id"] == "test_widget"
        assert data["type"] == "gauge"
        assert data["label"] == "Test Gauge"
        assert data["value"] == 50.0

    def test_widget_update(self):
        widget = Widget(
            widget_id="test_widget",
            widget_type=WidgetType.LABEL,
        )
        widget.update("new_value", color="#FF0000")
        assert widget.value == "new_value"
        assert widget.properties["color"] == "#FF0000"


class TestScreen:
    """Tests for Screen class."""

    def test_create_screen(self):
        screen = Screen("dashboard", "Dashboard", "🏠")
        assert screen.name == "dashboard"
        assert screen.title == "Dashboard"
        assert screen.icon == "🏠"
        assert len(screen.widgets) == 0

    def test_add_widget(self):
        screen = Screen("test", "Test Screen")
        widget = Widget(
            widget_id="widget1",
            widget_type=WidgetType.LABEL,
        )
        screen.add_widget(widget)
        assert "widget1" in screen.widgets
        assert screen.widgets["widget1"] == widget

    def test_remove_widget(self):
        screen = Screen("test", "Test Screen")
        widget = Widget(
            widget_id="widget1",
            widget_type=WidgetType.LABEL,
        )
        screen.add_widget(widget)
        screen.remove_widget("widget1")
        assert "widget1" not in screen.widgets

    def test_get_widget(self):
        screen = Screen("test", "Test Screen")
        widget = Widget(
            widget_id="widget1",
            widget_type=WidgetType.LABEL,
        )
        screen.add_widget(widget)
        retrieved = screen.get_widget("widget1")
        assert retrieved == widget

    def test_update_widget(self):
        screen = Screen("test", "Test Screen")
        widget = Widget(
            widget_id="widget1",
            widget_type=WidgetType.LABEL,
            value="initial",
        )
        screen.add_widget(widget)
        screen.update_widget("widget1", "updated")
        assert screen.widgets["widget1"].value == "updated"

    def test_to_dict(self):
        screen = Screen("test", "Test Screen")
        widget = Widget(
            widget_id="widget1",
            widget_type=WidgetType.LABEL,
        )
        screen.add_widget(widget)
        data = screen.to_dict()
        assert data["name"] == "test"
        assert data["title"] == "Test Screen"
        assert len(data["widgets"]) == 1


class TestScreenManager:
    """Tests for ScreenManager class."""

    def test_create_screen_manager(self):
        manager = ScreenManager()
        assert len(manager.screens) == 0
        assert manager.current_screen is None

    def test_create_screen(self):
        manager = ScreenManager()
        screen = manager.create_screen("dashboard", "Dashboard")
        assert "dashboard" in manager.screens
        assert screen.name == "dashboard"

    def test_get_screen(self):
        manager = ScreenManager()
        manager.create_screen("dashboard", "Dashboard")
        screen = manager.get_screen("dashboard")
        assert screen is not None
        assert screen.name == "dashboard"

    def test_set_current_screen(self):
        manager = ScreenManager()
        manager.create_screen("dashboard", "Dashboard")
        success = manager.set_current_screen("dashboard")
        assert success is True
        assert manager.current_screen == "dashboard"

    def test_set_current_screen_invalid(self):
        manager = ScreenManager()
        success = manager.set_current_screen("nonexistent")
        assert success is False

    def test_go_back(self):
        manager = ScreenManager()
        manager.create_screen("dashboard", "Dashboard")
        manager.create_screen("inverters", "Inverters")

        manager.set_current_screen("dashboard")
        manager.set_current_screen("inverters")

        success = manager.go_back()
        assert success is True
        assert manager.current_screen == "dashboard"

    def test_go_back_empty_history(self):
        manager = ScreenManager()
        success = manager.go_back()
        assert success is False

    def test_get_screens_list(self):
        manager = ScreenManager()
        manager.create_screen("dashboard", "Dashboard", "🏠")
        manager.create_screen("inverters", "Inverters", "⚡")

        screens_list = manager.get_screens_list()
        assert len(screens_list) == 2
        assert any(s["name"] == "dashboard" for s in screens_list)

    def test_to_dict(self):
        manager = ScreenManager()
        manager.create_screen("dashboard", "Dashboard")
        data = manager.to_dict()
        assert "current" in data
        assert "screens" in data
        assert "dashboard" in data["screens"]
