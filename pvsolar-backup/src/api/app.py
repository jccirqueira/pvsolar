from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.config import BackupConfig, load_config
from src.backup.engine import BackupEngine
from src.restore.engine import RestoreEngine
from src.scheduler.scheduler import BackupScheduler
from src.storage.backends import create_storage

config = load_config()
app = FastAPI(title=config.api.title, version="1.0.0")

backup_engine = BackupEngine(config)
restore_engine = RestoreEngine(config)
scheduler = BackupScheduler(config, backup_engine)
storage = create_storage(config.storage)


class BackupRequest(BaseModel):
    backup_id: str | None = None


class RestoreRequest(BaseModel):
    filepath: str
    destination: str


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pvsolar-backup"}


@app.post("/api/backup")
async def create_backup(req: BackupRequest | None = None):
    backup_id = req.backup_id if req else None
    record = await backup_engine.create_backup(backup_id)
    return record.to_dict()


@app.get("/api/backups")
async def list_backups():
    return [r.to_dict() for r in backup_engine.list_records()]


@app.get("/api/backups/{backup_id}")
async def get_backup(backup_id: str):
    record = backup_engine.get_record(backup_id)
    if not record:
        raise HTTPException(status_code=404, detail="Backup not found")
    return record.to_dict()


@app.delete("/api/backups/{backup_id}")
async def delete_backup(backup_id: str):
    if not backup_engine.delete_backup(backup_id):
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"deleted": backup_id}


@app.post("/api/restore")
async def restore_backup(req: RestoreRequest):
    result = await restore_engine.restore_backup(req.filepath, req.destination)
    return result.to_dict()


@app.get("/api/restore/contents/{filepath:path}")
async def list_archive_contents(filepath: str):
    contents = restore_engine.list_archive_contents(filepath)
    return {"files": contents}


@app.get("/api/schedule")
async def get_schedule():
    return scheduler.get_status()


@app.post("/api/schedule/run")
async def run_schedule_now():
    result = await scheduler.run_now()
    return result


@app.get("/api/statistics")
async def get_statistics():
    return backup_engine.get_statistics()


@app.get("/api/storage")
async def list_storage_files():
    files = await storage.list_files()
    return {"files": files}
