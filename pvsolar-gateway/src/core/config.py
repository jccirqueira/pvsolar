"""
Configuration module with Pydantic validation.
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class GatewaySettings(BaseModel):
    """Gateway core settings."""
    name: str = Field(..., description="Gateway unique identifier")
    location: str = Field(default="", description="Physical location")
    timezone: str = Field(default="UTC", description="Timezone")
    instance_id: Optional[str] = Field(default=None, description="Unique instance ID")


class TLSConfig(BaseModel):
    """TLS configuration."""
    enabled: bool = Field(default=True, description="Enable TLS")
    ca_cert: str = Field(default="", description="CA certificate path")
    client_cert: str = Field(default="", description="Client certificate path")
    client_key: str = Field(default="", description="Client key path")
    tls_version: str = Field(default="1.3", description="TLS version (1.2 or 1.3)")
    verify_certificate: bool = Field(default=True, description="Verify server certificate")


class MQTTConfig(BaseModel):
    """MQTT broker configuration."""
    broker: str = Field(..., description="MQTT broker hostname")
    port: int = Field(default=8883, description="MQTT port")
    use_tls: bool = Field(default=True, description="Use TLS encryption")
    tls: TLSConfig = Field(default_factory=TLSConfig)
    client_id: str = Field(..., description="MQTT client ID")
    username: Optional[str] = Field(default=None, description="MQTT username")
    password: Optional[str] = Field(default=None, description="MQTT password")
    
    topics: dict = Field(default_factory=lambda: {
        "publish": "pvsolar/{site_id}/telemetry",
        "command": "pvsolar/{site_id}/command",
        "status": "pvsolar/{site_id}/status",
        "alert": "pvsolar/{site_id}/alert"
    })
    
    qos: int = Field(default=1, ge=0, le=2)
    retain: bool = Field(default=True)
    heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds")
    reconnect_delay: int = Field(default=5, description="Reconnect delay in seconds")
    max_inflight: int = Field(default=20, description="Max inflight messages")
    max_queued: int = Field(default=1000, description="Max queued messages")


class ModbusConnection(BaseModel):
    """Modbus connection settings."""
    type: str = Field(default="modbus_tcp", description="Connection type (modbus_tcp or modbus_rtu)")
    host: str = Field(..., description="Modbus TCP host")
    port: int = Field(default=502, description="Modbus TCP port")
    unit_id: int = Field(default=1, ge=1, le=247, description="Modbus unit ID")
    timeout: float = Field(default=3.0, description="Connection timeout in seconds")
    retries: int = Field(default=3, description="Number of retries")


class RegisterConfig(BaseModel):
    """Modbus register configuration."""
    name: str = Field(..., description="Register name")
    address: int = Field(..., description="Register address")
    type: str = Field(default="uint16", description="Data type")
    scale: float = Field(default=1.0, description="Scaling factor")
    unit: str = Field(default="", description="Measurement unit")
    description: str = Field(default="", description="Register description")


class InverterConfig(BaseModel):
    """Inverter configuration."""
    id: str = Field(..., description="Inverter unique ID")
    name: str = Field(..., description="Inverter name")
    driver: str = Field(..., description="Driver type (sunspec, fronius, growatt, sma, huawei)")
    connection: ModbusConnection
    polling_interval: float = Field(default=5.0, description="Polling interval in seconds")
    registers: list[RegisterConfig] = Field(default_factory=list)
    
    @field_validator('driver')
    @classmethod
    def validate_driver(cls, v):
        valid_drivers = ['sunspec', 'fronius', 'growatt', 'sma', 'huawei', 'custom']
        if v not in valid_drivers:
            raise ValueError(f'Driver must be one of: {valid_drivers}')
        return v


class AWSIoTConfig(BaseModel):
    """AWS IoT Core configuration."""
    enabled: bool = Field(default=False)
    endpoint: str = Field(default="")
    cert_path: str = Field(default="")
    thing_name: str = Field(default="")
    region: str = Field(default="us-east-1")


class AzureIoTConfig(BaseModel):
    """Azure IoT Hub configuration."""
    enabled: bool = Field(default=False)
    connection_string: str = Field(default="")
    device_id: str = Field(default="")


class MQTTLocalConfig(BaseModel):
    """Local MQTT broker configuration."""
    enabled: bool = Field(default=True)
    broker: str = Field(default="localhost")
    port: int = Field(default=1883)


class CloudConfig(BaseModel):
    """Cloud integration configuration."""
    aws_iot: AWSIoTConfig = Field(default_factory=AWSIoTConfig)
    azure_iot: AzureIoTConfig = Field(default_factory=AzureIoTConfig)
    mqtt_local: MQTTLocalConfig = Field(default_factory=MQTTLocalConfig)


class StoreAndForwardConfig(BaseModel):
    """Edge store-and-forward configuration."""
    enabled: bool = Field(default=True)
    database: str = Field(default="/var/lib/pvsolar/edge.db")
    max_buffer_hours: int = Field(default=72)
    sync_interval: int = Field(default=30, description="Sync interval in seconds")
    max_records: int = Field(default=100000, description="Max records before drop")


class EdgeProcessingConfig(BaseModel):
    """Edge processing configuration."""
    enabled: bool = Field(default=True)
    aggregation: str = Field(default="1min")
    calculators: list[str] = Field(default_factory=lambda: ["performance_ratio"])


class EdgeConfig(BaseModel):
    """Edge computing configuration."""
    store_and_forward: StoreAndForwardConfig = Field(default_factory=StoreAndForwardConfig)
    processing: EdgeProcessingConfig = Field(default_factory=EdgeProcessingConfig)


class PVBrowserConfig(BaseModel):
    """pvbrowser integration configuration."""
    enabled: bool = Field(default=True)
    socket_port: int = Field(default=5050)
    shared_memory: bool = Field(default=True)
    update_interval: float = Field(default=1.0)


class WebAuthConfig(BaseModel):
    """Web dashboard authentication."""
    enabled: bool = Field(default=True)
    username: str = Field(default="admin")
    password_hash: str = Field(default="")
    jwt_secret: str = Field(default="")
    jwt_expiry_hours: int = Field(default=24)


class WebConfig(BaseModel):
    """Web dashboard configuration."""
    enabled: bool = Field(default=True)
    port: int = Field(default=5000)
    host: str = Field(default="0.0.0.0")
    auth: WebAuthConfig = Field(default_factory=WebAuthConfig)


class TelegramConfig(BaseModel):
    """Telegram alert configuration."""
    enabled: bool = Field(default=False)
    bot_token: str = Field(default="")
    chat_id: str = Field(default="")


class AlertsConfig(BaseModel):
    """Alerts configuration."""
    enabled: bool = Field(default=False)
    channels: dict = Field(default_factory=lambda: {
        "telegram": TelegramConfig(),
        "whatsapp": {"enabled": False},
        "sms": {"enabled": False}
    })


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO")
    file: str = Field(default="/var/log/pvsolar/gateway.log")
    max_size_mb: int = Field(default=100)
    backup_count: int = Field(default=10)
    format: str = Field(default="json")


class MetricsConfig(BaseModel):
    """Prometheus metrics configuration."""
    enabled: bool = Field(default=True)
    port: int = Field(default=9090)


class GatewayConfig(BaseModel):
    """Main gateway configuration."""
    gateway: GatewaySettings
    mqtt: MQTTConfig
    inverters: list[InverterConfig] = Field(default_factory=list)
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    edge: EdgeConfig = Field(default_factory=EdgeConfig)
    pvbrowser: PVBrowserConfig = Field(default_factory=PVBrowserConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)


def load_config(config_path: str) -> GatewayConfig:
    """Load and validate configuration from YAML file."""
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(path, 'r') as f:
        raw_config = yaml.safe_load(f)
    
    if raw_config is None:
        raise ValueError("Configuration file is empty")
    
    # Validate and create config
    config = GatewayConfig(**raw_config)
    
    return config


def create_default_config() -> dict:
    """Create a default configuration dictionary."""
    return {
        "gateway": {
            "name": "solar-site-001",
            "location": "",
            "timezone": "UTC"
        },
        "mqtt": {
            "broker": "localhost",
            "port": 8883,
            "use_tls": True,
            "client_id": "pvsolar-gateway-001",
            "topics": {
                "publish": "pvsolar/{site_id}/telemetry",
                "command": "pvsolar/{site_id}/command",
                "status": "pvsolar/{site_id}/status"
            }
        },
        "inverters": [],
        "edge": {
            "store_and_forward": {
                "enabled": True,
                "database": "/var/lib/pvsolar/edge.db"
            }
        }
    }
