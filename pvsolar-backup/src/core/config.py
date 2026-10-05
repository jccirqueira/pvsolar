import os
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class StorageType(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    FTP = "ftp"
    SMB = "smb"
    AZURE = "azure"
    GCS = "gcs"


class CompressionType(StrEnum):
    NONE = "none"
    GZIP = "gzip"
    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"


class ScheduleFrequency(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class BackupStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RetentionConfig(BaseModel):
    max_backups: int = Field(default=30, ge=1)
    max_age_days: int = Field(default=90, ge=1)
    min_keep: int = Field(default=5, ge=1)


class StorageConfig(BaseModel):
    type: StorageType = StorageType.LOCAL
    local_path: str = Field(default="./backups")
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_prefix: str = "backups/"
    ftp_host: str = ""
    ftp_port: int = 21
    ftp_user: str = ""
    ftp_password: str = ""
    ftp_path: str = "/backups"
    smb_host: str = ""
    smb_share: str = ""
    smb_user: str = ""
    smb_password: str = ""
    azure_connection: str = ""
    azure_container: str = ""
    gcs_bucket: str = ""
    gcs_credentials: str = ""


class ScheduleConfig(BaseModel):
    enabled: bool = True
    frequency: ScheduleFrequency = ScheduleFrequency.DAILY
    time: str = "02:00"
    day_of_week: int = 0
    day_of_month: int = 1
    cron_expression: str = ""


class DataSourceConfig(BaseModel):
    gateway_url: str = "http://localhost:8000"
    analytics_url: str = "http://localhost:8001"
    scada_url: str = "http://localhost:5000"
    reports_url: str = "http://localhost:8002"
    fleet_url: str = "http://localhost:8003"
    alert_url: str = "http://localhost:8004"
    grid_url: str = "http://localhost:8005"
    twin_url: str = "http://localhost:8006"
    auth_url: str = "http://localhost:8007"
    database_path: str = "data/"
    config_path: str = "config/"


class NotificationConfig(BaseModel):
    enabled: bool = False
    email_on_success: bool = True
    email_on_failure: bool = True
    webhook_url: str = ""


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8008
    title: str = "pvSolar Backup API"


class BackupConfig(BaseModel):
    storage: StorageConfig = Field(default_factory=StorageConfig)
    compression: CompressionType = CompressionType.TAR_GZ
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    data_sources: DataSourceConfig = Field(default_factory=DataSourceConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    company_name: str = "pvSolar Backup"
    debug: bool = False


def load_config(path: str | None = None) -> BackupConfig:
    """Carrega a configuracao.

    Precedencia: argumento explicito > variavel ``PVSOLAR_CONFIG`` >
    ``config/backup.yaml`` (ou .yml) no diretorio atual > padroes do codigo.
    """
    if path is None:
        path = os.environ.get("PVSOLAR_CONFIG")
    if path is None:
        for candidate in ("config/backup.yaml", "config/backup.yml"):
            if Path(candidate).exists():
                path = candidate
                break
    if path is None:
        return BackupConfig()
    try:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return BackupConfig(**data)
    except FileNotFoundError:
        return BackupConfig()
