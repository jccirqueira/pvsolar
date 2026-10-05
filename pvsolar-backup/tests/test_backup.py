import os
import tempfile
from pathlib import Path

import pytest
from src.backup.engine import BackupEngine, BackupRecord
from src.core.config import BackupConfig, BackupStatus, CompressionType


@pytest.fixture
def tmp_backup_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def config_with_files(tmp_backup_dir):
    db_dir = Path(tmp_backup_dir) / "data"
    db_dir.mkdir()
    (db_dir / "test.db").write_text("fake database content")
    cfg_dir = Path(tmp_backup_dir) / "config"
    cfg_dir.mkdir()
    (cfg_dir / "settings.yaml").write_text("key: value")

    return BackupConfig(
        storage={"local_path": str(Path(tmp_backup_dir) / "backups")},
        data_sources={"database_path": str(db_dir), "config_path": str(cfg_dir)},
        compression=CompressionType.ZIP,
    )


@pytest.fixture
def config_empty(tmp_backup_dir):
    return BackupConfig(
        storage={"local_path": str(Path(tmp_backup_dir) / "backups")},
        data_sources={"database_path": "/nonexistent", "config_path": "/nonexistent2"},
    )


class TestBackupRecord:
    def test_create_record(self):
        r = BackupRecord("b1", "2024-01-01T00:00:00", BackupStatus.COMPLETED, 5, 1024, "abc123")
        assert r.backup_id == "b1"
        assert r.files_count == 5
        assert r.size_bytes == 1024

    def test_to_dict(self):
        r = BackupRecord("b1", "2024-01-01T00:00:00", BackupStatus.COMPLETED)
        d = r.to_dict()
        assert d["backup_id"] == "b1"
        assert d["status"] == "completed"


class TestBackupEngine:
    def test_generate_backup_id(self, config_with_files):
        engine = BackupEngine(config_with_files)
        bid = engine.generate_backup_id()
        assert bid.startswith("backup_")

    def test_create_backup(self, config_with_files):
        engine = BackupEngine(config_with_files)
        import asyncio
        record = asyncio.get_event_loop().run_until_complete(engine.create_backup())
        assert record.status == BackupStatus.COMPLETED
        assert record.files_count > 0
        assert record.size_bytes > 0

    def test_create_backup_with_id(self, config_with_files):
        engine = BackupEngine(config_with_files)
        import asyncio
        record = asyncio.get_event_loop().run_until_complete(engine.create_backup("my_backup"))
        assert record.backup_id == "my_backup"
        assert record.status == BackupStatus.COMPLETED

    def test_empty_backup(self, config_empty):
        engine = BackupEngine(config_empty)
        import asyncio
        record = asyncio.get_event_loop().run_until_complete(engine.create_backup())
        assert record.status == BackupStatus.COMPLETED

    def test_get_record(self, config_with_files):
        engine = BackupEngine(config_with_files)
        import asyncio
        asyncio.get_event_loop().run_until_complete(engine.create_backup("test_id"))
        record = engine.get_record("test_id")
        assert record is not None
        assert record.backup_id == "test_id"

    def test_list_records(self, config_with_files):
        engine = BackupEngine(config_with_files)
        import asyncio
        asyncio.get_event_loop().run_until_complete(engine.create_backup("backup_1"))
        asyncio.get_event_loop().run_until_complete(engine.create_backup("backup_2"))
        assert len(engine.list_records()) == 2

    def test_delete_backup(self, config_with_files):
        engine = BackupEngine(config_with_files)
        import asyncio
        asyncio.get_event_loop().run_until_complete(engine.create_backup("del_test"))
        assert engine.delete_backup("del_test") is True
        assert engine.get_record("del_test") is None

    def test_delete_nonexistent(self, config_with_files):
        engine = BackupEngine(config_with_files)
        assert engine.delete_backup("nonexistent") is False

    def test_statistics(self, config_with_files):
        engine = BackupEngine(config_with_files)
        import asyncio
        asyncio.get_event_loop().run_until_complete(engine.create_backup())
        stats = engine.get_statistics()
        assert stats["total_backups"] == 1
        assert stats["completed"] == 1
        assert stats["total_size_bytes"] > 0
