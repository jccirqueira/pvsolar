"""
Screen Factory.

Creates and configures all SCADA screens.
"""

from typing import Optional

from src.core.config import SCADAConfig
from src.core.screens import ScreenManager
from src.screens.alarms import create_alarms_screen
from src.screens.dashboard import create_dashboard_screen
from src.screens.inverters import create_inverter_screen
from src.screens.performance import create_performance_screen
from src.screens.trends import create_trends_screen
from src.screens.weather import create_weather_screen

import structlog

logger = structlog.get_logger(__name__)


class ScreenFactory:
    """Factory for creating SCADA screens."""
    
    def __init__(self, config: SCADAConfig):
        self.config = config
        self.screen_manager = ScreenManager()
    
    def create_all_screens(self) -> ScreenManager:
        """Create all configured screens."""
        logger.info("screenfactory.creating_screens")
        
        create_dashboard_screen(self.screen_manager)
        create_inverter_screen(self.screen_manager, self.config.plant.num_inverters)
        create_weather_screen(self.screen_manager)
        create_alarms_screen(self.screen_manager)
        create_trends_screen(self.screen_manager)
        create_performance_screen(self.screen_manager)
        
        self.screen_manager.set_current_screen("dashboard")
        
        logger.info(
            "screenfactory.screens_created",
            count=len(self.screen_manager.screens),
            screens=list(self.screen_manager.screens.keys()),
        )
        
        return self.screen_manager
