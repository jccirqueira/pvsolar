"""
Tests for pvSolar SCADA Screen Factory and Application.
"""

from src.core.config import SCADAConfig
from src.core.screens import ScreenManager
from src.screens.factory import ScreenFactory


class TestScreenFactory:
    """Tests for ScreenFactory class."""

    def setup_method(self):
        self.config = SCADAConfig()

    def test_create_factory(self):
        factory = ScreenFactory(self.config)
        assert factory.config == self.config
        assert isinstance(factory.screen_manager, ScreenManager)

    def test_create_all_screens(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        assert isinstance(manager, ScreenManager)
        assert len(manager.screens) >= 5

    def test_dashboard_screen_created(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        assert "dashboard" in manager.screens

    def test_inverter_screen_created(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        assert "inverters" in manager.screens

    def test_weather_screen_created(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        assert "weather" in manager.screens

    def test_alarms_screen_created(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        assert "alarms" in manager.screens

    def test_trends_screen_created(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        assert "trends" in manager.screens

    def test_performance_screen_created(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        assert "performance" in manager.screens

    def test_current_screen_is_dashboard(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        assert manager.current_screen == "dashboard"

    def test_dashboard_has_widgets(self):
        factory = ScreenFactory(self.config)
        manager = factory.create_all_screens()
        dashboard = manager.get_screen("dashboard")
        assert len(dashboard.widgets) > 10

    def test_inverter_screen_widgets_per_inverter(self):
        config = SCADAConfig()
        config.plant.num_inverters = 3
        factory = ScreenFactory(config)
        manager = factory.create_all_screens()
        inverter_screen = manager.get_screen("inverters")
        assert len(inverter_screen.widgets) > 5
