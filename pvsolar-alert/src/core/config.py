"""Configuração central do pvSolar Alert."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    WEBHOOK = "webhook"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class EscalationLevel(str, Enum):
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    LEVEL_4 = "level_4"


class TimeWindow(str, Enum):
    BUSINESS_HOURS = "business_hours"
    AFTER_HOURS = "after_hours"
    WEEKEND = "weekend"
    ALWAYS = "always"


# ---------------------------------------------------------------------------
# Config Models
# ---------------------------------------------------------------------------

class ChannelConfig(BaseModel):
    enabled: bool = Field(default=False)
    api_key: Optional[str] = Field(default=None)
    api_secret: Optional[str] = Field(default=None)
    from_address: Optional[str] = Field(default=None)
    from_name: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)
    bot_token: Optional[str] = Field(default=None)
    chat_id: Optional[str] = Field(default=None)
    account_sid: Optional[str] = Field(default=None)
    auth_token: Optional[str] = Field(default=None)
    from_number: Optional[str] = Field(default=None)
    webhook_url: Optional[str] = Field(default=None)
    timeout: int = Field(default=30)


class RecipientConfig(BaseModel):
    name: str = Field(default="")
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    telegram_chat_id: Optional[str] = Field(default=None)
    whatsapp_number: Optional[str] = Field(default=None)
    channels: list[NotificationChannel] = Field(default_factory=list)
    time_window: TimeWindow = Field(default=TimeWindow.ALWAYS)


class EscalationContact(BaseModel):
    name: str = Field(default="")
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    telegram_chat_id: Optional[str] = Field(default=None)
    whatsapp_number: Optional[str] = Field(default=None)
    channels: list[NotificationChannel] = Field(default_factory=list)


class EscalationRuleConfig(BaseModel):
    level: EscalationLevel = Field(default=EscalationLevel.LEVEL_1)
    wait_seconds: int = Field(default=300)
    contacts: list[EscalationContact] = Field(default_factory=list)


class NotificationConfig(BaseModel):
    max_per_hour: int = Field(default=50)
    max_per_day: int = Field(default=200)
    retry_attempts: int = Field(default=3)
    retry_delay_seconds: int = Field(default=60)
    batch_size: int = Field(default=10)
    batch_delay_seconds: int = Field(default=5)


class RuleCondition(BaseModel):
    field: str = Field(default="")
    operator: str = Field(default="eq")
    value: float = Field(default=0.0)


class AlertRuleConfig(BaseModel):
    id: str = Field(default="")
    name: str = Field(default="")
    enabled: bool = Field(default=True)
    conditions: list[RuleCondition] = Field(default_factory=list)
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM)
    channels: list[NotificationChannel] = Field(default_factory=list)
    recipients: list[str] = Field(default_factory=list)
    escalation_level: EscalationLevel = Field(default=EscalationLevel.LEVEL_1)
    time_window: TimeWindow = Field(default=TimeWindow.ALWAYS)
    cooldown_seconds: int = Field(default=300)


class DatabaseConfig(BaseModel):
    path: str = Field(default="data/alerts.db")


class APIConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8004)
    title: str = Field(default="pvSolar Alert API")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="json")


class AlertConfig(BaseModel):
    email: ChannelConfig = Field(default_factory=ChannelConfig)
    sms: ChannelConfig = Field(default_factory=ChannelConfig)
    telegram: ChannelConfig = Field(default_factory=ChannelConfig)
    whatsapp: ChannelConfig = Field(default_factory=ChannelConfig)
    webhook: ChannelConfig = Field(default_factory=ChannelConfig)
    recipients: list[RecipientConfig] = Field(default_factory=list)
    escalation: list[EscalationRuleConfig] = Field(default_factory=list)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    rules: list[AlertRuleConfig] = Field(default_factory=list)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    company_name: str = Field(default="pvSolar Alert")
    debug: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path | None = None) -> AlertConfig:
    """Carrega config do arquivo YAML ou retorna padrão."""
    if config_path is None:
        return AlertConfig()

    path = Path(config_path)
    if not path.exists():
        return AlertConfig()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return AlertConfig(**data)
