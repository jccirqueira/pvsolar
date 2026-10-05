"""
Configuration module with Pydantic validation.
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class MQTTConfig(BaseModel):
    """MQTT consumer configuration."""
    broker: str = Field(..., description="MQTT broker hostname")
    port: int = Field(default=8883, description="MQTT port")
    use_tls: bool = Field(default=True, description="Use TLS encryption")
    tls_enabled: bool = Field(default=True, description="TLS enabled")
    ca_cert: str = Field(default="", description="CA certificate path")
    client_cert: str = Field(default="", description="Client certificate path")
    client_key: str = Field(default="", description="Client key path")
    client_id: str = Field(..., description="MQTT client ID")
    username: Optional[str] = Field(default=None, description="MQTT username")
    password: Optional[str] = Field(default=None, description="MQTT password")
    subscribe_topics: list[str] = Field(
        default_factory=lambda: [
            "pvsolar/+/telemetry/+",
            "pvsolar/+/status",
            "pvsolar/+/alert",
        ],
        description="MQTT topics to subscribe"
    )
    qos: int = Field(default=1, ge=0, le=2, description="MQTT QoS level")
    reconnect_delay: int = Field(default=5, description="Reconnect delay seconds")


class DatabaseConfig(BaseModel):
    """TimescaleDB configuration."""
    url: str = Field(
        default="postgresql+asyncpg://analytics:password@localhost:5432/pvsolar_analytics",
        description="Database URL"
    )
    pool_size: int = Field(default=10, ge=1, le=100, description="Connection pool size")
    echo: bool = Field(default=False, description="SQLAlchemy echo")


class RedisConfig(BaseModel):
    """Redis configuration."""
    url: str = Field(default="redis://localhost:6379/0", description="Redis URL")


class AnomalyConfig(BaseModel):
    """Anomaly detection configuration."""
    contamination: float = Field(default=0.05, ge=0.01, le=0.5)
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    retrain_interval_hours: int = Field(default=168, description="Retrain every N hours")


class MaintenanceConfig(BaseModel):
    """Predictive maintenance configuration."""
    prediction_horizons: list[int] = Field(
        default_factory=lambda: [7, 30, 90],
        description="Prediction horizons in days"
    )
    retrain_interval_hours: int = Field(default=168)


class ForecastConfig(BaseModel):
    """Energy forecasting configuration."""
    horizon_hours: int = Field(default=168, description="Forecast horizon in hours")
    confidence_level: float = Field(default=0.95, ge=0.8, le=0.99)


class MLConfig(BaseModel):
    """Machine learning configuration."""
    model_dir: str = Field(default="./ml_models", description="Model storage directory")
    anomaly: AnomalyConfig = Field(default_factory=AnomalyConfig)
    maintenance: MaintenanceConfig = Field(default_factory=MaintenanceConfig)
    forecast: ForecastConfig = Field(default_factory=ForecastConfig)


class AlertChannelConfig(BaseModel):
    """Alert channel configuration."""
    enabled: bool = Field(default=False)


class TelegramAlertConfig(AlertChannelConfig):
    """Telegram alert configuration."""
    bot_token: str = Field(default="")
    chat_id: str = Field(default="")


class EmailAlertConfig(AlertChannelConfig):
    """Email alert configuration."""
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    username: str = Field(default="")
    password: str = Field(default="")
    from_addr: str = Field(default="")
    to_addrs: list[str] = Field(default_factory=list)


class AlertsConfig(BaseModel):
    """Alerts configuration."""
    enabled: bool = Field(default=True)
    telegram: TelegramAlertConfig = Field(default_factory=TelegramAlertConfig)
    email: EmailAlertConfig = Field(default_factory=EmailAlertConfig)


class APIConfig(BaseModel):
    """API configuration."""
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


class WebConfig(BaseModel):
    """Web dashboard configuration."""
    enabled: bool = Field(default=True)
    dashboard_port: int = Field(default=8001)


class WorkerConfig(BaseModel):
    """Celery worker configuration."""
    enabled: bool = Field(default=True)
    concurrency: int = Field(default=4, ge=1, le=32)


class AnalyticsConfig(BaseModel):
    """Root configuration model."""
    mqtt: MQTTConfig
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)


def load_config(path: str) -> AnalyticsConfig:
    """Load and validate configuration from YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AnalyticsConfig(**raw)


def create_default_config() -> dict:
    """Create a default configuration dictionary."""
    return {
        "mqtt": {
            "broker": "localhost",
            "port": 1883,
            "use_tls": False,
            "tls_enabled": False,
            "client_id": "pvsolar-analytics-001",
            "qos": 1,
        },
        "database": {
            "url": "postgresql+asyncpg://analytics:password@localhost:5432/pvsolar_analytics",
            "pool_size": 10,
        },
        "redis": {
            "url": "redis://localhost:6379/0",
        },
        "ml": {
            "model_dir": "./ml_models",
        },
        "api": {
            "host": "0.0.0.0",
            "port": 8000,
        },
    }
