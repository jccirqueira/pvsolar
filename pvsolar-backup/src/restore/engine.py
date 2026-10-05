import gzip
import tarfile
import zipfile
from pathlib import Path

import structlog

from src.core.config import BackupConfig, CompressionType

logger = structlog.get_logger()


class RestoreResult:
    def __init__(self, success: bool, files_restored: int = 0,
                 destination: str = "", error: str = "", duration_seconds: float = 0.0):
        self.success = success
        self.files_restored = files_restored
        self.destination = destination
        self.error = error
        self.duration_seconds = duration_seconds

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "files_restored": self.files_restored,
            "destination": self.destination,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


class RestoreEngine:
    def __init__(self, config: BackupConfig):
        self.config = config

    def _detect_compression(self, filepath: str) -> CompressionType:
        p = Path(filepath)
        if p.suffix == ".zip":
            return CompressionType.ZIP
        elif p.suffix == ".gz":
            return CompressionType.GZIP
        elif p.suffix == ".tar":
            return CompressionType.TAR
        elif filepath.endswith(".tar.gz"):
            return CompressionType.TAR_GZ
        return CompressionType.NONE

    def _restore_zip(self, filepath: str, destination: str) -> int:
        count = 0
        with zipfile.ZipFile(filepath, 'r') as zf:
            zf.extractall(destination)
            count = len(zf.namelist())
        return count

    def _restore_gzip(self, filepath: str, destination: str) -> int:
        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)
        out_file = dest_path / "restored_file"
        with gzip.open(filepath, 'rb') as gz_f, open(out_file, 'wb') as out_f:
            out_f.write(gz_f.read())
        return 1

    def _restore_tar(self, filepath: str, destination: str, mode: str = "r:*") -> int:
        count = 0
        with tarfile.open(filepath, mode) as tf:
            tf.extractall(destination)
            count = len(tf.getnames())
        return count

    async def restore_backup(self, filepath: str, destination: str) -> RestoreResult:
        import time
        start = time.time()

        if not Path(filepath).exists():
            return RestoreResult(success=False, error=f"File not found: {filepath}")

        try:
            compression = self._detect_compression(filepath)
            dest_path = Path(destination)
            dest_path.mkdir(parents=True, exist_ok=True)

            if compression == CompressionType.ZIP:
                count = self._restore_zip(filepath, destination)
            elif compression == CompressionType.GZIP:
                count = self._restore_gzip(filepath, destination)
            elif compression == CompressionType.TAR_GZ:
                count = self._restore_tar(filepath, destination, "r:gz")
            elif compression == CompressionType.TAR:
                count = self._restore_tar(filepath, destination, "r:")
            else:
                import shutil
                shutil.copy2(filepath, str(dest_path / Path(filepath).name))
                count = 1

            duration = time.time() - start
            logger.info("restore.completed", files=count, destination=destination)
            return RestoreResult(success=True, files_restored=count,
                                 destination=destination, duration_seconds=duration)
        except Exception as e:
            duration = time.time() - start
            logger.error("restore.failed", error=str(e))
            return RestoreResult(success=False, error=str(e), duration_seconds=duration)

    def list_archive_contents(self, filepath: str) -> list[str]:
        if not Path(filepath).exists():
            return []

        compression = self._detect_compression(filepath)
        try:
            if compression == CompressionType.ZIP:
                with zipfile.ZipFile(filepath, 'r') as zf:
                    return zf.namelist()
            elif compression in (CompressionType.TAR_GZ, CompressionType.TAR):
                mode = "r:gz" if compression == CompressionType.TAR_GZ else "r"
                with tarfile.open(filepath, mode) as tf:
                    return tf.getnames()
        except Exception:
            return []
        return []
