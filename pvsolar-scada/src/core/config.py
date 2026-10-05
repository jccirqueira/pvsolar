"""
pvSolar SCADA Configuration.

Centralized configuration using Pydantic for type-safe settings.
"""

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class ScreenType(StrEnum):
    """SCADA screen types."""
    DASHBOARD = "dashboard"
    INVERTERS = "inverters"
    WEATHER = "weather"
    ALARMS = "alarms"
    TRENDS = "trends"
    MAINTENANCE = "maintenance"
    PERFORMANCE = "performance"
    SETTINGS = "settings"


class WidgetType(StrEnum):
    """pvBrowser widget types."""
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


class MQTTConfig(BaseSettings):
    """MQTT connection settings."""
    broker: str = Field(default="localhost", description="MQTT broker host")
    port: int = Field(default=1883, description="MQTT broker port")
    username: str | None = Field(default=None, description="MQTT username")
    password: str | None = Field(default=None, description="MQTT password")
    client_id: str = Field(default="pvsolar-scada", description="MQTT client ID")
    topics: list[str] = Field(
        default=[
            "pvsolar/+/telemetry",
            "pvsolar/+/status",
            "pvsolar/+/alarms",
        ],
        description="MQTT topics to subscribe"
    )
    qos: int = Field(default=1, ge=0, le=2, description="MQTT QoS level")
    tls: bool = Field(default=False, description="Enable TLS")
    ca_cert: str | None = Field(default=None, description="CA certificate path")

    model_config = {"env_prefix": "MQTT_"}


class PVBrowserConfig(BaseSettings):
    """pvBrowser server configuration."""
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=5000, description="Server port")
    max_clients: int = Field(default=10, ge=1, le=100, description="Max clients")
    update_interval: float = Field(default=1.0, ge=0.1, le=60.0, description="Update interval in seconds")
    title: str = Field(default="pvSolar SCADA", description="Window title")

    model_config = {"env_prefix": "PVBROWSER_"}


class GatewayConfig(BaseSettings):
    """Gateway connection settings."""
    url: str = Field(default="http://localhost:8000", description="Gateway API URL")
    mqtt_bridge_port: int = Field(default=1884, description="Gateway MQTT bridge port")
    api_key: str | None = Field(default=None, description="API key")

    model_config = {"env_prefix": "GATEWAY_"}


class AnalyticsConfig(BaseSettings):
    """Analytics service settings."""
    url: str = Field(default="http://localhost:8001", description="Analytics API URL")
    api_key: str | None = Field(default=None, description="API key")

    model_config = {"env_prefix": "ANALYTICS_"}


class AlarmConfig(BaseSettings):
    """Alarm configuration."""
    levels: dict[str, str] = Field(
        default={
            "critical": "#FF0000",
            "warning": "#FFA500",
            "info": "#0000FF",
            "ok": "#00FF00",
        },
        description="Alarm level colors"
    )
    max_alarms: int = Field(default=1000, ge=100, le=10000, description="Max alarms to keep")
    sound_enabled: bool = Field(default=True, description="Enable alarm sounds")
    acknowledge_timeout: int = Field(default=300, ge=30, description="Auto-ack timeout in seconds")

    model_config = {"env_prefix": "ALARM_"}


class TrendConfig(BaseSettings):
    """Trend/chart configuration."""
    max_points: int = Field(default=3600, ge=100, le=86400, description="Max trend points")
    update_rate: float = Field(default=1.0, ge=0.1, le=60.0, description="Trend update rate in seconds")
    time_ranges: list[str] = Field(
        default=["1h", "6h", "24h", "7d", "30d"],
        description="Available time ranges"
    )

    model_config = {"env_prefix": "TREND_"}


class PlantConfig(BaseSettings):
    """Solar plant configuration."""
    name: str = Field(default="Solar Plant", description="Plant name")
    capacity_kw: float = Field(default=100.0, gt=0, description="Plant capacity in kW")
    num_inverters: int = Field(default=1, ge=1, le=100, description="Number of inverters")
    timezone: str = Field(default="America/Sao_Paulo", description="Plant timezone")
    latitude: float = Field(default=-23.55, ge=-90, le=90, description="Plant latitude")
    longitude: float = Field(default=-46.63, ge=-180, le=180, description="Plant longitude")

    model_config = {"env_prefix": "PLANT_"}


class SCADAConfig(BaseSettings):
    """Main SCADA configuration."""
    mqtt: MQTTConfig = Field(default_factory=MQTTConfig)
    pvbrowser: PVBrowserConfig = Field(default_factory=PVBrowserConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    alarms: AlarmConfig = Field(default_factory=AlarmConfig)
    trends: TrendConfig = Field(default_factory=TrendConfig)
    plant: PlantConfig = Field(default_factory=PlantConfig)

    screens: list[ScreenType] = Field(
        default=[
            ScreenType.DASHBOARD,
            ScreenType.INVERTERS,
            ScreenType.WEATHER,
            ScreenType.ALARMS,
            ScreenType.TRENDS,
            ScreenType.PERFORMANCE,
        ],
        description="Enabled screens"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    model_config = {"env_prefix": "PVSCADA_"}

    @field_validator("screens", mode="before")
    @classmethod
    def validate_screens(cls, v: Any) -> list[ScreenType]:
        if isinstance(v, list):
            return [ScreenType(s) if isinstance(s, str) else s for s in v]
        return v


def load_config(config_path: str | None = None) -> SCADAConfig:
    """Load configuration from file and environment."""
    from pathlib import Path

    import yaml

    config_data: dict[str, Any] = {}

    if config_path:
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                config_data = yaml.safe_load(f) or {}
    else:
        default_paths = [
            Path("config/scada.yaml"),
            Path("config/scada.yml"),
            Path.home() / ".pvsolar" / "scada.yaml",
        ]
        for path in default_paths:
            if path.exists():
                with open(path) as f:
                    config_data = yaml.safe_load(f) or {}
                break

    return SCADAConfig(**config_data)
