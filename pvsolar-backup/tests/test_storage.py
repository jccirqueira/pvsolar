import os
import tempfile
from pathlib import Path

import pytest
from src.core.config import StorageConfig, StorageType
from src.storage.backends import (
    AzureStorage,
    FTPStorage,
    GCSStorage,
    LocalStorage,
    S3Storage,
    SMBStorage,
    create_storage,
)


@pytest.fixture
def tmp_storage_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def local_config(tmp_storage_dir):
    return StorageConfig(type=StorageType.LOCAL, local_path=tmp_storage_dir)


class TestLocalStorage:
    def test_upload(self, local_config, tmp_storage_dir):
        src = os.path.join(tmp_storage_dir, "source.txt")
        with open(src, 'w') as f:
            f.write("test content")
        storage = LocalStorage(local_config)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            storage.upload(src, "dest.txt")
        )
        assert result is True

    def test_download(self, local_config, tmp_storage_dir):
        src = os.path.join(tmp_storage_dir, "source.txt")
        with open(src, 'w') as f:
            f.write("test content")
        storage = LocalStorage(local_config)
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            storage.upload(src, "uploaded.txt")
        )
        dest = os.path.join(tmp_storage_dir, "downloaded.txt")
        result = asyncio.get_event_loop().run_until_complete(
            storage.download("uploaded.txt", dest)
        )
        assert result is True
        assert os.path.exists(dest)

    def test_list_files(self, local_config, tmp_storage_dir):
        storage = LocalStorage(local_config)
        import asyncio
        Path(os.path.join(tmp_storage_dir, "f1.txt")).touch()
        files = asyncio.get_event_loop().run_until_complete(storage.list_files())
        assert len(files) >= 1

    def test_exists(self, local_config, tmp_storage_dir):
        storage = LocalStorage(local_config)
        import asyncio
        Path(os.path.join(tmp_storage_dir, "exists.txt")).touch()
        assert asyncio.get_event_loop().run_until_complete(storage.exists("exists.txt")) is True
        assert asyncio.get_event_loop().run_until_complete(storage.exists("no.txt")) is False

    def test_delete(self, local_config, tmp_storage_dir):
        storage = LocalStorage(local_config)
        Path(os.path.join(tmp_storage_dir, "del.txt")).touch()
        import asyncio
        assert asyncio.get_event_loop().run_until_complete(storage.delete("del.txt")) is True
        assert asyncio.get_event_loop().run_until_complete(storage.delete("del.txt")) is False


class TestCreateStorage:
    def test_local(self, local_config):
        storage = create_storage(local_config)
        assert isinstance(storage, LocalStorage)

    def test_ftp(self):
        config = StorageConfig(type=StorageType.FTP, ftp_host="localhost")
        storage = create_storage(config)
        assert isinstance(storage, FTPStorage)

    def test_s3(self):
        config = StorageConfig(type=StorageType.S3, s3_bucket="bucket")
        storage = create_storage(config)
        assert isinstance(storage, S3Storage)

    def test_smb(self):
        config = StorageConfig(type=StorageType.SMB, smb_host="localhost")
        storage = create_storage(config)
        assert isinstance(storage, SMBStorage)

    def test_azure(self):
        config = StorageConfig(type=StorageType.AZURE, azure_connection="conn")
        storage = create_storage(config)
        assert isinstance(storage, AzureStorage)

    def test_gcs(self):
        config = StorageConfig(type=StorageType.GCS, gcs_bucket="bucket")
        storage = create_storage(config)
        assert isinstance(storage, GCSStorage)
