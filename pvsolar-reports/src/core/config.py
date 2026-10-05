"""
pvSolar Reports Configuration.

Centralized configuration using Pydantic for type-safe settings.
"""

import os
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class ReportType(StrEnum):
    """Report types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    MAINTENANCE = "maintenance"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class OutputFormat(StrEnum):
    """Output formats."""
    PDF = "pdf"
    EXCEL = "excel"
    HTML = "html"
    ALL = "all"


class ReportLanguage(StrEnum):
    """Report languages."""
    PT_BR = "pt_BR"
    EN_US = "en_US"


class GatewayConfig(BaseSettings):
    """Gateway API connection settings."""
    url: str = Field(default="http://localhost:8000", description="Gateway API URL")
    api_key: str | None = Field(default=None, description="API key")
    timeout: int = Field(default=30, ge=5, le=120, description="Request timeout in seconds")

    model_config = {"env_prefix": "GATEWAY_"}


class AnalyticsConfig(BaseSettings):
    """Analytics API connection settings."""
    url: str = Field(default="http://localhost:8001", description="Analytics API URL")
    api_key: str | None = Field(default=None, description="API key")
    timeout: int = Field(default=30, ge=5, le=120, description="Request timeout in seconds")

    model_config = {"env_prefix": "ANALYTICS_"}


class EmailConfig(BaseSettings):
    """Email notification settings."""
    enabled: bool = Field(default=False, description="Enable email notifications")
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP host")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_user: str | None = Field(default=None, description="SMTP username")
    smtp_password: str | None = Field(default=None, description="SMTP password")
    use_tls: bool = Field(default=True, description="Use TLS")
    from_address: str = Field(default="reports@pvsolar.com", description="From address")
    recipients: list[str] = Field(default_factory=list, description="Recipient addresses")

    model_config = {"env_prefix": "EMAIL_"}


class SchedulerConfig(BaseSettings):
    """Scheduler configuration."""
    enabled: bool = Field(default=True, description="Enable scheduler")
    daily_time: str = Field(default="06:00", description="Daily report time (HH:MM)")
    weekly_day: int = Field(default=1, ge=0, le=6, description="Weekly report day (0=Mon)")
    monthly_day: int = Field(default=1, ge=1, le=28, description="Monthly report day")

    model_config = {"env_prefix": "SCHEDULER_"}


class OutputConfig(BaseSettings):
    """Output directory settings."""
    base_dir: str = Field(default="output", description="Base output directory")
    pdf_dir: str = Field(default="output/pdf", description="PDF output directory")
    excel_dir: str = Field(default="output/excel", description="Excel output directory")
    retention_days: int = Field(default=90, ge=7, le=365, description="File retention in days")

    model_config = {"env_prefix": "OUTPUT_"}


class TemplateConfig(BaseSettings):
    """Template settings."""
    language: ReportLanguage = Field(default=ReportLanguage.PT_BR, description="Report language")
    company_name: str = Field(default="pvSolar Energy", description="Company name")
    company_logo: str | None = Field(default=None, description="Logo path")
    primary_color: str = Field(default="#10B981", description="Primary color")
    secondary_color: str = Field(default="#3B82F6", description="Secondary color")

    model_config = {"env_prefix": "TEMPLATE_"}


class PlantConfig(BaseSettings):
    """Solar plant configuration."""
    name: str = Field(default="Solar Plant", description="Plant name")
    capacity_kw: float = Field(default=100.0, gt=0, description="Plant capacity in kW")
    num_inverters: int = Field(default=1, ge=1, le=100, description="Number of inverters")
    timezone: str = Field(default="America/Sao_Paulo", description="Plant timezone")

    model_config = {"env_prefix": "PLANT_"}


class APIConfig(BaseSettings):
    """FastAPI server settings."""
    host: str = Field(default="0.0.0.0", description="API bind host")
    port: int = Field(default=8002, description="API port")
    title: str = Field(default="pvSolar Reports API", description="API title")

    model_config = {"env_prefix": "API_"}


class ReportsConfig(BaseSettings):
    """Main reports configuration."""
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    template: TemplateConfig = Field(default_factory=TemplateConfig)
    plant: PlantConfig = Field(default_factory=PlantConfig)
    api: APIConfig = Field(default_factory=APIConfig)

    formats: list[OutputFormat] = Field(
        default=[OutputFormat.PDF, OutputFormat.EXCEL],
        description="Default output formats"
    )
    report_types: list[ReportType] = Field(
        default=[ReportType.DAILY, ReportType.WEEKLY, ReportType.MONTHLY],
        description="Enabled report types"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    model_config = {"env_prefix": "PVREPORTS_"}


def load_config(config_path: str | None = None) -> ReportsConfig:
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
            Path("config/reports.yaml"),
            Path("config/reports.yml"),
            Path.home() / ".pvsolar" / "reports.yaml",
        ]
        for path in default_paths:
            if path.exists():
                with open(path) as f:
                    config_data = yaml.safe_load(f) or {}
                break

    return ReportsConfig(**config_data)
