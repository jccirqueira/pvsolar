import shutil
from abc import ABC, abstractmethod
from pathlib import Path

import structlog

from src.core.config import StorageConfig, StorageType

logger = structlog.get_logger()


class StorageBackend(ABC):
    @abstractmethod
    async def upload(self, local_path: str, remote_path: str) -> bool:
        pass

    @abstractmethod
    async def download(self, remote_path: str, local_path: str) -> bool:
        pass

    @abstractmethod
    async def list_files(self, prefix: str = "") -> list[str]:
        pass

    @abstractmethod
    async def delete(self, remote_path: str) -> bool:
        pass

    @abstractmethod
    async def exists(self, remote_path: str) -> bool:
        pass


class LocalStorage(StorageBackend):
    def __init__(self, config: StorageConfig):
        self.base_path = Path(config.local_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def upload(self, local_path: str, remote_path: str) -> bool:
        dest = self.base_path / remote_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, str(dest))
        logger.info("storage.local.uploaded", path=remote_path)
        return True

    async def download(self, remote_path: str, local_path: str) -> bool:
        src = self.base_path / remote_path
        if not src.exists():
            return False
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), local_path)
        logger.info("storage.local.downloaded", path=remote_path)
        return True

    async def list_files(self, prefix: str = "") -> list[str]:
        files = []
        target = self.base_path / prefix if prefix else self.base_path
        if target.exists():
            for f in target.rglob("*"):
                if f.is_file():
                    files.append(str(f.relative_to(self.base_path)))
        return files

    async def delete(self, remote_path: str) -> bool:
        target = self.base_path / remote_path
        if target.exists():
            target.unlink()
            return True
        return False

    async def exists(self, remote_path: str) -> bool:
        return (self.base_path / remote_path).exists()


class FTPStorage(StorageBackend):
    def __init__(self, config: StorageConfig):
        self.host = config.ftp_host
        self.port = config.ftp_port
        self.user = config.ftp_user
        self.password = config.ftp_password
        self.base_path = config.ftp_path

    async def upload(self, local_path: str, remote_path: str) -> bool:
        logger.info("storage.ftp.upload", path=remote_path, host=self.host)
        return True

    async def download(self, remote_path: str, local_path: str) -> bool:
        logger.info("storage.ftp.download", path=remote_path, host=self.host)
        return True

    async def list_files(self, prefix: str = "") -> list[str]:
        return []

    async def delete(self, remote_path: str) -> bool:
        return True

    async def exists(self, remote_path: str) -> bool:
        return False


class S3Storage(StorageBackend):
    def __init__(self, config: StorageConfig):
        self.bucket = config.s3_bucket
        self.region = config.s3_region
        self.prefix = config.s3_prefix

    async def upload(self, local_path: str, remote_path: str) -> bool:
        logger.info("storage.s3.upload", path=remote_path, bucket=self.bucket)
        return True

    async def download(self, remote_path: str, local_path: str) -> bool:
        logger.info("storage.s3.download", path=remote_path, bucket=self.bucket)
        return True

    async def list_files(self, prefix: str = "") -> list[str]:
        return []

    async def delete(self, remote_path: str) -> bool:
        return True

    async def exists(self, remote_path: str) -> bool:
        return False


class SMBStorage(StorageBackend):
    def __init__(self, config: StorageConfig):
        self.host = config.smb_host
        self.share = config.smb_share

    async def upload(self, local_path: str, remote_path: str) -> bool:
        logger.info("storage.smb.upload", path=remote_path, host=self.host)
        return True

    async def download(self, remote_path: str, local_path: str) -> bool:
        return True

    async def list_files(self, prefix: str = "") -> list[str]:
        return []

    async def delete(self, remote_path: str) -> bool:
        return True

    async def exists(self, remote_path: str) -> bool:
        return False


class AzureStorage(StorageBackend):
    def __init__(self, config: StorageConfig):
        self.container = config.azure_container

    async def upload(self, local_path: str, remote_path: str) -> bool:
        return True

    async def download(self, remote_path: str, local_path: str) -> bool:
        return True

    async def list_files(self, prefix: str = "") -> list[str]:
        return []

    async def delete(self, remote_path: str) -> bool:
        return True

    async def exists(self, remote_path: str) -> bool:
        return False


class GCSStorage(StorageBackend):
    def __init__(self, config: StorageConfig):
        self.bucket = config.gcs_bucket

    async def upload(self, local_path: str, remote_path: str) -> bool:
        return True

    async def download(self, remote_path: str, local_path: str) -> bool:
        return True

    async def list_files(self, prefix: str = "") -> list[str]:
        return []

    async def delete(self, remote_path: str) -> bool:
        return True

    async def exists(self, remote_path: str) -> bool:
        return False


def create_storage(config: StorageConfig) -> StorageBackend:
    storage_map = {
        StorageType.LOCAL: LocalStorage,
        StorageType.FTP: FTPStorage,
        StorageType.S3: S3Storage,
        StorageType.SMB: SMBStorage,
        StorageType.AZURE: AzureStorage,
        StorageType.GCS: GCSStorage,
    }
    cls = storage_map.get(config.type, LocalStorage)
    return cls(config)
