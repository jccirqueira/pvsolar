import gzip
import hashlib
import json
import shutil
import tarfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from src.core.config import BackupConfig, BackupStatus, CompressionType

logger = structlog.get_logger()


class BackupRecord:
    def __init__(self, backup_id: str, timestamp: str, status: BackupStatus,
                 files_count: int = 0, size_bytes: int = 0, checksum: str = "",
                 error: str = "", duration_seconds: float = 0.0):
        self.backup_id = backup_id
        self.timestamp = timestamp
        self.status = status
        self.files_count = files_count
        self.size_bytes = size_bytes
        self.checksum = checksum
        self.error = error
        self.duration_seconds = duration_seconds

    def to_dict(self) -> dict:
        return {
            "backup_id": self.backup_id,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "files_count": self.files_count,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


class BackupEngine:
    def __init__(self, config: BackupConfig):
        self.config = config
        self.records: dict[str, BackupRecord] = {}

    def generate_backup_id(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"backup_{ts}"

    def _collect_files(self) -> list[tuple[str, str]]:
        files = []
        ds = self.config.data_sources
        for path_str in [ds.database_path, ds.config_path]:
            p = Path(path_str)
            if p.exists():
                if p.is_dir():
                    for f in p.rglob("*"):
                        if f.is_file():
                            files.append((str(f), f.name))
                else:
                    files.append((str(p), p.name))
        return files

    def _compress_files(self, files: list[tuple[str, str]], output_path: str,
                        compression: CompressionType) -> str:
        if compression == CompressionType.ZIP:
            archive_path = output_path + ".zip"
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for src, name in files:
                    zf.write(src, name)
            return archive_path
        elif compression == CompressionType.GZIP:
            archive_path = output_path + ".gz"
            with open(archive_path, 'wb') as out_f:
                with gzip.GzipFile(fileobj=out_f, mode='wb') as gz_f:
                    for src, _ in files:
                        with open(src, 'rb') as in_f:
                            gz_f.write(in_f.read())
            return archive_path
        elif compression in (CompressionType.TAR, CompressionType.TAR_GZ):
            ext = ".tar.gz" if compression == CompressionType.TAR_GZ else ".tar"
            archive_path = output_path + ext
            mode = "w:gz" if compression == CompressionType.TAR_GZ else "w"
            with tarfile.open(archive_path, mode) as tf:
                for src, name in files:
                    tf.add(src, arcname=name)
            return archive_path
        else:
            archive_path = output_path + ".raw"
            if files:
                shutil.copy2(files[0][0], archive_path)
            return archive_path

    def _calculate_checksum(self, filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    async def create_backup(self, backup_id: str | None = None) -> BackupRecord:
        if backup_id is None:
            backup_id = self.generate_backup_id()

        ts = datetime.now(timezone.utc).isoformat()
        record = BackupRecord(backup_id=backup_id, timestamp=ts, status=BackupStatus.RUNNING)
        self.records[backup_id] = record

        logger.info("backup.started", backup_id=backup_id)
        start_time = time.time()

        try:
            files = self._collect_files()
            if not files:
                record.status = BackupStatus.COMPLETED
                record.error = "No files to backup"
                logger.warning("backup.no_files", backup_id=backup_id)
                return record

            storage_path = Path(self.config.storage.local_path)
            storage_path.mkdir(parents=True, exist_ok=True)
            output_path = str(storage_path / backup_id)

            archive_path = self._compress_files(files, output_path, self.config.compression)
            record.files_count = len(files)
            record.size_bytes = Path(archive_path).stat().st_size
            record.checksum = self._calculate_checksum(archive_path)
            record.duration_seconds = time.time() - start_time
            record.status = BackupStatus.COMPLETED

            logger.info("backup.completed", backup_id=backup_id,
                        files=record.files_count, size=record.size_bytes)
        except Exception as e:
            record.status = BackupStatus.FAILED
            record.error = str(e)
            record.duration_seconds = time.time() - start_time
            logger.error("backup.failed", backup_id=backup_id, error=str(e))

        return record

    def get_record(self, backup_id: str) -> BackupRecord | None:
        return self.records.get(backup_id)

    def list_records(self) -> list[BackupRecord]:
        return list(self.records.values())

    def delete_backup(self, backup_id: str) -> bool:
        if backup_id not in self.records:
            return False
        storage_path = Path(self.config.storage.local_path)
        for ext in [".zip", ".gz", ".tar.gz", ".tar", ".raw"]:
            f = storage_path / (backup_id + ext)
            if f.exists():
                f.unlink()
        del self.records[backup_id]
        logger.info("backup.deleted", backup_id=backup_id)
        return True

    def get_statistics(self) -> dict:
        records = self.list_records()
        total_size = sum(r.size_bytes for r in records)
        return {
            "total_backups": len(records),
            "completed": sum(1 for r in records if r.status == BackupStatus.COMPLETED),
            "failed": sum(1 for r in records if r.status == BackupStatus.FAILED),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
