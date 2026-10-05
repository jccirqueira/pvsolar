import os
import tempfile

import pytest
from src.core.config import (
    APIConfig,
    BackupConfig,
    BackupStatus,
    CompressionType,
    DataSourceConfig,
    NotificationConfig,
    RetentionConfig,
    ScheduleConfig,
    ScheduleFrequency,
    StorageConfig,
    StorageType,
    load_config,
)


class TestEnums:
    def test_storage_type(self):
        assert StorageType.LOCAL == "local"
        assert StorageType.S3 == "s3"
        assert StorageType.FTP == "ftp"

    def test_compression_type(self):
        assert CompressionType.ZIP == "zip"
        assert CompressionType.GZIP == "gzip"
        assert CompressionType.TAR_GZ == "tar.gz"
        assert CompressionType.NONE == "none"

    def test_schedule_frequency(self):
        assert ScheduleFrequency.DAILY == "daily"
        assert ScheduleFrequency.WEEKLY == "weekly"
        assert ScheduleFrequency.MONTHLY == "monthly"

    def test_backup_status(self):
        assert BackupStatus.PENDING == "pending"
        assert BackupStatus.RUNNING == "running"
        assert BackupStatus.COMPLETED == "completed"
        assert BackupStatus.FAILED == "failed"
        assert BackupStatus.CANCELLED == "cancelled"


class TestRetentionConfig:
    def test_defaults(self):
        c = RetentionConfig()
        assert c.max_backups == 30
        assert c.max_age_days == 90
        assert c.min_keep == 5

    def test_custom(self):
        c = RetentionConfig(max_backups=10, max_age_days=30, min_keep=2)
        assert c.max_backups == 10
        assert c.max_age_days == 30
        assert c.min_keep == 2


class TestStorageConfig:
    def test_defaults(self):
        c = StorageConfig()
        assert c.type == StorageType.LOCAL
        assert c.local_path == "./backups"

    def test_s3_config(self):
        c = StorageConfig(type=StorageType.S3, s3_bucket="my-bucket", s3_region="us-east-1")
        assert c.type == StorageType.S3
        assert c.s3_bucket == "my-bucket"


class TestScheduleConfig:
    def test_defaults(self):
        c = ScheduleConfig()
        assert c.enabled is True
        assert c.frequency == ScheduleFrequency.DAILY
        assert c.time == "02:00"

    def test_disabled(self):
        c = ScheduleConfig(enabled=False)
        assert c.enabled is False


class TestBackupConfig:
    def test_defaults(self):
        c = BackupConfig()
        assert c.compression == CompressionType.TAR_GZ
        assert c.debug is False

    def test_api_config(self):
        c = BackupConfig(api=APIConfig(port=9000))
        assert c.api.port == 9000


class TestLoadConfig:
    def test_load_default(self):
        c = load_config()
        assert isinstance(c, BackupConfig)

    def test_load_nonexistent(self):
        c = load_config("nonexistent.yaml")
        assert isinstance(c, BackupConfig)

    def test_load_via_env_pvsolar_config(self, tmp_path, monkeypatch):
        cfg = tmp_path / "custom.yaml"
        cfg.write_text('company_name: "BACKUP_VIA_ENV"\n', encoding="utf-8")
        monkeypatch.setenv("PVSOLAR_CONFIG", str(cfg))
        c = load_config()
        assert c.company_name == "BACKUP_VIA_ENV"
