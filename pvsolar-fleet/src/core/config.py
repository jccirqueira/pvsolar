"""
pvSolar Fleet Configuration.

Centralized configuration using Pydantic for type-safe settings.
"""

import os
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class SiteStatus(StrEnum):
    """Site status."""
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    DEGRADED = "degraded"


class AlertSeverity(StrEnum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(StrEnum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ComparisonMetric(StrEnum):
    """Metrics for comparison."""
    ENERGY = "energy"
    PR = "pr"
    EFFICIENCY = "efficiency"
    AVAILABILITY = "availability"
    CEF = "cef"
    SCORE = "score"


class SiteConfig(BaseSettings):
    """Individual site configuration."""
    id: str = Field(description="Site unique ID")
    name: str = Field(description="Site name")
    gateway_url: str = Field(description="Gateway API URL")
    analytics_url: str = Field(description="Analytics API URL")
    capacity_kw: float = Field(gt=0, description="Site capacity in kW")
    num_inverters: int = Field(ge=1, description="Number of inverters")
    timezone: str = Field(default="America/Sao_Paulo", description="Site timezone")
    latitude: float = Field(ge=-90, le=90, description="Latitude")
    longitude: float = Field(ge=-180, le=180, description="Longitude")
    region: str = Field(default="default", description="Site region")
    api_key: str | None = Field(default=None, description="API key")

    model_config = {"env_prefix": "SITE_"}


class GatewayServiceConfig(BaseSettings):
    """Gateway service connection settings."""
    url: str = Field(default="http://localhost:8000", description="Gateway service URL")
    api_key: str | None = Field(default=None, description="API key")
    timeout: int = Field(default=30, ge=5, le=120, description="Request timeout")

    model_config = {"env_prefix": "GATEWAY_"}


class AnalyticsServiceConfig(BaseSettings):
    """Analytics service connection settings."""
    url: str = Field(default="http://localhost:8001", description="Analytics service URL")
    api_key: str | None = Field(default=None, description="API key")
    timeout: int = Field(default=30, ge=5, le=120, description="Request timeout")

    model_config = {"env_prefix": "ANALYTICS_"}


class AlertAggregatorConfig(BaseSettings):
    """Alert aggregator settings."""
    enabled: bool = Field(default=True, description="Enable alert aggregation")
    max_alerts_per_site: int = Field(default=100, ge=10, le=1000, description="Max alerts per site")
    escalation_timeout: int = Field(default=300, ge=60, description="Escalation timeout in seconds")
    auto_resolve_timeout: int = Field(default=3600, ge=300, description="Auto-resolve timeout")

    model_config = {"env_prefix": "ALERT_"}


class ComparisonConfig(BaseSettings):
    """Comparison engine settings."""
    enabled: bool = Field(default=True, description="Enable comparison engine")
    default_metric: ComparisonMetric = Field(default=ComparisonMetric.PR, description="Default comparison metric")
    ranking_window: int = Field(default=30, ge=1, le=365, description="Ranking window in days")
    peer_group_size: int = Field(default=5, ge=2, le=50, description="Peer group size")

    model_config = {"env_prefix": "COMPARISON_"}


class APIConfig(BaseSettings):
    """FastAPI server settings."""
    host: str = Field(default="0.0.0.0", description="API bind host")
    port: int = Field(default=8003, description="API port")
    title: str = Field(default="pvSolar Fleet API", description="API title")
    debug: bool = Field(default=False, description="Debug mode")

    model_config = {"env_prefix": "API_"}


class FleetConfig(BaseSettings):
    """Main fleet configuration."""
    gateway: GatewayServiceConfig = Field(default_factory=GatewayServiceConfig)
    analytics: AnalyticsServiceConfig = Field(default_factory=AnalyticsServiceConfig)
    alerts: AlertAggregatorConfig = Field(default_factory=AlertAggregatorConfig)
    comparison: ComparisonConfig = Field(default_factory=ComparisonConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    sites: list[SiteConfig] = Field(default_factory=list, description="Managed sites")
    company_name: str = Field(default="pvSolar Fleet", description="Company name")
    debug: bool = Field(default=False, description="Debug mode")

    model_config = {"env_prefix": "PVFLEET_"}


def load_config(config_path: str | None = None) -> FleetConfig:
    """Load configuration from file and environment."""
    import yaml

    config_data: dict[str, Any] = {}

    if config_path:
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                config_data = yaml.safe_load(f) or {}
    else:
        default_paths = []
        env_path = os.environ.get("PVSOLAR_CONFIG")
        if env_path:
            default_paths.append(Path(env_path))
        default_paths += [
            Path("config/fleet.yaml"),
            Path("config/fleet.yml"),
            Path.home() / ".pvsolar" / "fleet.yaml",
        ]
        for path in default_paths:
            if path.exists():
                with open(path) as f:
                    config_data = yaml.safe_load(f) or {}
                break

    return FleetConfig(**config_data)
