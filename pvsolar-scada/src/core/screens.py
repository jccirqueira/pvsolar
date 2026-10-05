"""
Screen Manager Module.

Manages SCADA screens and their widgets.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class WidgetType(str, Enum):
    """SCADA widget types."""
    GAUGE = "gauge"
    CHART = "chart"
    LABEL = "label"
    BUTTON = "button"
    INDICATOR = "indicator"
    TABLE = "table"
    IMAGE = "image"
    LED = "led"
    THERMOMETER = "thermometer"
    PROGRESS = "progress"
    GROUP = "group"
    COMBOBOX = "combobox"
    LINEEDIT = "lineedit"
    CHECKBOX = "checkbox"
    COMPASS = "compass"


class Widget:
    """Represents a SCADA widget."""
    
    def __init__(
        self,
        widget_id: str,
        widget_type: WidgetType,
        label: str = "",
        x: int = 0,
        y: int = 0,
        width: int = 100,
        height: int = 60,
        **properties: Any,
    ):
        self.widget_id = widget_id
        self.widget_type = widget_type
        self.label = label
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.properties = properties
        self.value: Any = None
        self.visible = True
        self.enabled = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert widget to dictionary."""
        return {
            "id": self.widget_id,
            "type": self.widget_type.value,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "value": self.value,
            "visible": self.visible,
            "enabled": self.enabled,
            **self.properties,
        }
    
    def update(self, value: Any, **properties: Any) -> None:
        """Update widget value and properties."""
        self.value = value
        for key, val in properties.items():
            self.properties[key] = val


class Screen:
    """Represents a SCADA screen with widgets."""
    
    def __init__(self, name: str, title: str, icon: str = ""):
        self.name = name
        self.title = title
        self.icon = icon
        self.widgets: Dict[str, Widget] = {}
        self.groups: Dict[str, List[str]] = {}
        self.layout: Dict[str, Any] = {}
        self.on_load: Optional[Callable] = None
        self.on_refresh: Optional[Callable] = None
    
    def add_widget(self, widget: Widget) -> None:
        """Add a widget to the screen."""
        self.widgets[widget.widget_id] = widget
        logger.debug("screen.widget_added", screen=self.name, widget=widget.widget_id)
    
    def remove_widget(self, widget_id: str) -> None:
        """Remove a widget from the screen."""
        self.widgets.pop(widget_id, None)
    
    def get_widget(self, widget_id: str) -> Optional[Widget]:
        """Get a widget by ID."""
        return self.widgets.get(widget_id)
    
    def update_widget(self, widget_id: str, value: Any, **properties: Any) -> None:
        """Update a widget's value."""
        widget = self.widgets.get(widget_id)
        if widget:
            widget.update(value, **properties)
    
    def add_group(self, group_name: str, widget_ids: List[str]) -> None:
        """Add a group of widgets."""
        self.groups[group_name] = widget_ids
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert screen to dictionary."""
        return {
            "name": self.name,
            "title": self.title,
            "icon": self.icon,
            "widgets": [w.to_dict() for w in self.widgets.values()],
            "groups": self.groups,
            "layout": self.layout,
        }


class ScreenManager:
    """Manages all SCADA screens."""
    
    def __init__(self):
        self.screens: Dict[str, Screen] = {}
        self.current_screen: Optional[str] = None
        self._screen_history: List[str] = []
    
    def create_screen(self, name: str, title: str, icon: str = "") -> Screen:
        """Create a new screen."""
        screen = Screen(name, title, icon)
        self.screens[name] = screen
        logger.info("screen.created", name=name, title=title)
        return screen
    
    def get_screen(self, name: str) -> Optional[Screen]:
        """Get a screen by name."""
        return self.screens.get(name)
    
    def set_current_screen(self, name: str) -> bool:
        """Set the current active screen."""
        if name in self.screens:
            if self.current_screen:
                self._screen_history.append(self.current_screen)
            self.current_screen = name
            logger.info("screen.activated", name=name)
            return True
        return False
    
    def go_back(self) -> bool:
        """Go to previous screen."""
        if self._screen_history:
            self.current_screen = self._screen_history.pop()
            return True
        return False
    
    def get_screens_list(self) -> List[Dict[str, str]]:
        """Get list of all screens with titles."""
        return [
            {"name": s.name, "title": s.title, "icon": s.icon}
            for s in self.screens.values()
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert all screens to dictionary."""
        return {
            "current": self.current_screen,
            "screens": {name: s.to_dict() for name, s in self.screens.items()},
        }
