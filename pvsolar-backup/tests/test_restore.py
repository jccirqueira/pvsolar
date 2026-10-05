import os
import tarfile
import tempfile
import zipfile
from pathlib import Path

import pytest
from src.core.config import BackupConfig, CompressionType
from src.restore.engine import RestoreEngine, RestoreResult


@pytest.fixture
def tmp_restore_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_zip(tmp_restore_dir):
    zip_path = os.path.join(tmp_restore_dir, "sample.zip")
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("file1.txt", "content1")
        zf.writestr("file2.txt", "content2")
    return zip_path


@pytest.fixture
def sample_tar_gz(tmp_restore_dir):
    tar_path = os.path.join(tmp_restore_dir, "sample.tar.gz")
    with tarfile.open(tar_path, 'w:gz') as tf:
        import io
        for name in ["file1.txt", "file2.txt"]:
            data = f"content of {name}".encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return tar_path


@pytest.fixture
def config(tmp_restore_dir):
    return BackupConfig(storage={"local_path": tmp_restore_dir})


class TestRestoreResult:
    def test_success(self):
        r = RestoreResult(True, 5, "/dest")
        assert r.success is True
        assert r.files_restored == 5

    def test_failure(self):
        r = RestoreResult(False, error="not found")
        assert r.success is False
        assert r.error == "not found"

    def test_to_dict(self):
        r = RestoreResult(True, 3, "/dest")
        d = r.to_dict()
        assert d["success"] is True
        assert d["files_restored"] == 3


class TestRestoreEngine:
    def test_restore_zip(self, config, sample_zip, tmp_restore_dir):
        engine = RestoreEngine(config)
        dest = os.path.join(tmp_restore_dir, "restored")
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            engine.restore_backup(sample_zip, dest)
        )
        assert result.success is True
        assert result.files_restored == 2

    def test_restore_nonexistent(self, config):
        engine = RestoreEngine(config)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            engine.restore_backup("/nonexistent/file.zip", "/tmp/dest")
        )
        assert result.success is False
        assert "not found" in result.error

    def test_list_zip_contents(self, config, sample_zip):
        engine = RestoreEngine(config)
        contents = engine.list_archive_contents(sample_zip)
        assert len(contents) == 2
        assert "file1.txt" in contents

    def test_list_nonexistent_contents(self, config):
        engine = RestoreEngine(config)
        contents = engine.list_archive_contents("/nonexistent/file.zip")
        assert contents == []
