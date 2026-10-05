"""Testes da camada de persistência do pvSolar Scheduler (PostgreSQL).

Roda por padrão em SQLite (aiosqlite) para ser reproduzível em qualquer
máquina. Para validar contra um PostgreSQL real:

    set PVSOLAR_TEST_DB_URL=postgresql+asyncpg://postgres:senha@localhost:5432/pvsolar_scheduler_test
    .\\venv\\Scripts\\python.exe -m pytest tests/test_persistence.py -q

ATENCAO: o schema e dropado/criado a cada teste. Use SEMPRE um banco
dedicado de testes (o sufixo ``_test`` e criado por
``scripts\\create_databases.py``) e nunca aponte ``PVSOLAR_TEST_DB_URL``
para o banco de producao.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from src.api.app import create_app
from src.core.config import (
    DatabaseConfig,
    ScheduleType,
    SchedulerConfig,
    TaskConfig,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from src.db.base import Base, create_engine
from src.db.models import TaskResultRow
from src.db.service import PersistenceService, _safe_url
from src.engine.scheduler import SchedulerEngine
from src.tasks.task import TaskRegistry, TaskResult

TEST_URL = os.environ.get("PVSOLAR_TEST_DB_URL", "").strip()


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def db_url(tmp_path) -> str:
    """URL de banco do teste (PostgreSQL via env ou SQLite temporário)."""
    if TEST_URL:
        return TEST_URL
    return f"sqlite+aiosqlite:///{tmp_path.as_posix()}/pvsolar_sched_test.db"


def make_config(url: str) -> DatabaseConfig:
    return DatabaseConfig(enabled=True, url=url, create_tables=True)


def scheduler_config(url: str, **kwargs) -> SchedulerConfig:
    return SchedulerConfig(database=make_config(url), **kwargs)


async def reset_schema(url: str) -> None:
    """Dropa as tabelas (isolamento entre testes em banco persistente)."""
    engine = create_engine(DatabaseConfig(enabled=True, url=url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def start_service(url: str) -> PersistenceService:
    service = PersistenceService(make_config(url))
    await service.startup()
    return service


async def count_rows(url: str, model) -> int:
    """Conta linhas de uma tabela sem passar pelo serviço."""
    engine = create_engine(DatabaseConfig(enabled=True, url=url))
    try:
        async with engine.connect() as conn:
            result = await conn.scalar(select(func.count()).select_from(model))
            return int(result or 0)
    finally:
        await engine.dispose()


def sample_config(task_id: str = "t-1") -> TaskConfig:
    return TaskConfig(
        id=task_id,
        name="Backup Noturno",
        task_type=TaskType.BACKUP_RUN,
        description="Backup dos dados de telemetria",
        enabled=True,
        priority=TaskPriority.HIGH,
        schedule_type=ScheduleType.DAILY,
        time="02:30",
        target_service="backup",
        target_url="http://localhost:8008/api/backup",
        payload={"nivel": "full", "destino": "s3"},
        timeout_seconds=600,
        max_retries=5,
        retry_delay_seconds=30,
        depends_on=["health_check"],
        tags=["backup", "noturno"],
    )


# ---------------------------------------------------------------------------
# Ciclo de vida
# ---------------------------------------------------------------------------

class TestStartup:
    async def test_disabled_is_noop(self):
        service = PersistenceService(DatabaseConfig(enabled=False, url=""))
        await service.startup()
        assert service.enabled is False
        assert service.started is False
        assert await service.ping() is False
        await service.save_result(TaskResult("t1", TaskStatus.COMPLETED))
        await service.delete_task("qualquer")
        assert await service.prune_history(10) == 0

    async def test_startup_creates_tables(self, tmp_path):
        url = db_url(tmp_path)
        service = await start_service(url)
        assert service.started is True
        assert await service.ping() is True
        await service.dispose()
        assert service.started is False

    async def test_hydrate_without_startup_raises(self):
        service = PersistenceService(make_config("sqlite+aiosqlite://"))
        with pytest.raises(RuntimeError, match="startup"):
            await service.hydrate(TaskRegistry(), SchedulerEngine(SchedulerConfig(), TaskRegistry()))

    def test_safe_url_masks_password(self):
        url = "postgresql+asyncpg://postgres:senha_secreta@localhost:5432/pvsolar_scheduler"
        masked = _safe_url(url)
        assert "senha_secreta" not in masked
        assert "postgres:***@localhost:5432" in masked


# ---------------------------------------------------------------------------
# Tarefas
# ---------------------------------------------------------------------------

class TestTaskPersistence:
    async def test_roundtrip_preserves_config_and_state(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        registry = TaskRegistry()
        task = registry.add_task(sample_config())
        task.status = TaskStatus.COMPLETED
        task.last_run = datetime.now(timezone.utc).isoformat()
        task.next_run = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()
        task.run_count = 7
        task.failure_count = 2
        await service.save_task(task)

        # novo "processo"
        registry2, engine2 = TaskRegistry(), SchedulerEngine(SchedulerConfig(), TaskRegistry())
        stats = await service.hydrate(registry2, engine2)

        got = registry2.get_task("t-1")
        assert got is not None
        cfg = got.config
        assert cfg.name == "Backup Noturno"
        assert cfg.task_type == TaskType.BACKUP_RUN
        assert cfg.priority == TaskPriority.HIGH
        assert cfg.schedule_type == ScheduleType.DAILY
        assert cfg.time == "02:30"
        assert cfg.target_url == "http://localhost:8008/api/backup"
        assert cfg.payload == {"nivel": "full", "destino": "s3"}
        assert cfg.timeout_seconds == 600
        assert cfg.max_retries == 5
        assert cfg.retry_delay_seconds == 30
        assert cfg.depends_on == ["health_check"]
        assert cfg.tags == ["backup", "noturno"]
        # estado de execução
        assert got.status == TaskStatus.COMPLETED
        assert got.run_count == 7
        assert got.failure_count == 2
        assert got.last_run is not None
        # timestamps normalizados com fuso (obrigatório para _should_run)
        next_dt = datetime.fromisoformat(got.next_run)
        assert next_dt.tzinfo is not None
        assert next_dt > datetime.now(timezone.utc)
        assert stats == {"tasks": 1, "results": 0}
        await service.dispose()

    async def test_save_updates_existing_row(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        registry = TaskRegistry()
        task = registry.add_task(sample_config())
        await service.save_task(task)

        registry.update_task("t-1", name="Backup Acelerado", interval_seconds=120)
        task = registry.get_task("t-1")
        task.run_count = 3
        await service.save_task(task)

        registry2, engine2 = TaskRegistry(), SchedulerEngine(SchedulerConfig(), TaskRegistry())
        await service.hydrate(registry2, engine2)
        got = registry2.get_task("t-1")
        assert got.config.name == "Backup Acelerado"
        assert got.config.interval_seconds == 120
        assert got.run_count == 3
        assert await count_rows(url, TaskResultRow) == 0  # nada duplicado
        await service.dispose()

    async def test_delete_removes_task_and_history(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        registry = TaskRegistry()
        task = registry.add_task(sample_config())
        await service.save_task(task)
        for i in range(3):
            await service.save_result(
                TaskResult("t-1", TaskStatus.COMPLETED, output={"i": i})
            )
        assert await count_rows(url, TaskResultRow) == 3

        await service.delete_task("t-1")

        registry2, engine2 = TaskRegistry(), SchedulerEngine(SchedulerConfig(), TaskRegistry())
        stats = await service.hydrate(registry2, engine2)
        assert stats == {"tasks": 0, "results": 0}
        assert registry2.get_task("t-1") is None
        assert engine2.history == []
        assert await count_rows(url, TaskResultRow) == 0
        await service.dispose()

    async def test_history_roundtrip(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        await service.save_result(
            TaskResult("t-1", TaskStatus.COMPLETED, output={"ok": True},
                       duration_seconds=1.25, retries=1)
        )
        await service.save_result(
            TaskResult("t-1", TaskStatus.FAILED, error="timeout na API",
                       duration_seconds=30.0, retries=3)
        )

        registry, engine = TaskRegistry(), SchedulerEngine(SchedulerConfig(), TaskRegistry())
        await service.hydrate(registry, engine)

        assert len(engine.history) == 2
        ok, failed = engine.history
        assert ok.status == TaskStatus.COMPLETED
        assert ok.output == {"ok": True}
        assert ok.duration_seconds == 1.25
        assert ok.retries == 1
        assert failed.status == TaskStatus.FAILED
        assert failed.error == "timeout na API"
        # ordem cronológica preservada
        assert datetime.fromisoformat(ok.timestamp) <= datetime.fromisoformat(failed.timestamp)
        await service.dispose()

    async def test_non_serializable_output_is_wrapped(self, tmp_path):
        """Saidas arbitrárias de handlers não podem quebrar a gravação."""
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        class ObjetoQualquer:
            pass

        await service.save_result(
            TaskResult("t-1", TaskStatus.COMPLETED, output={"obj": ObjetoQualquer()})
        )

        registry, engine = TaskRegistry(), SchedulerEngine(SchedulerConfig(), TaskRegistry())
        await service.hydrate(registry, engine)
        output = engine.history[0].output
        # apenas o objeto problemático é substituído; o resto é preservado
        assert output["obj"]["_type"] == "ObjetoQualquer"
        assert "_repr" in output["obj"]
        await service.dispose()

    async def test_prune_history_respects_max(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        for i in range(25):
            await service.save_result(TaskResult("t-1", TaskStatus.COMPLETED, output={"i": i}))
        assert await count_rows(url, TaskResultRow) == 25

        deleted = await service.prune_history(10)
        assert deleted == 15
        assert await count_rows(url, TaskResultRow) == 10
        # idempotente
        assert await service.prune_history(10) == 0
        await service.dispose()


# ---------------------------------------------------------------------------
# Fim a fim (API + lifespan + reinício simulado)
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_task_created_via_api_survives_restart(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        with TestClient(create_app(scheduler_config(url))) as c1:
            resp = c1.post(
                "/api/tasks",
                json={
                    "name": "Sync Inversores",
                    "task_type": "data_sync",
                    "interval_seconds": 300,
                    "tags": ["modbus"],
                    "payload": {"site": "usina-norte"},
                },
            )
            assert resp.status_code == 200
            task_id = resp.json()["id"]
            assert len(c1.get("/api/tasks").json()) == 1

        # "reinício": nova aplicação apontando para o mesmo banco
        with TestClient(create_app(scheduler_config(url))) as c2:
            tasks = c2.get("/api/tasks").json()
            assert len(tasks) == 1
            got = c2.get(f"/api/tasks/{task_id}").json()
            assert got["name"] == "Sync Inversores"
            assert got["tags"] == ["modbus"]
            assert got["task_type"] == "data_sync"
            assert got["priority"] == "normal"
            # payload/interval_seconds são persistidos (ver roundtrip unitário),
            # mas a representação exposta pela API não os inclui.
            assert c2.get(f"/api/tasks/{task_id}").status_code == 200

    def test_execution_state_and_history_survive_restart(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        with TestClient(create_app(scheduler_config(url))) as c1:
            task_id = c1.post("/api/tasks", json={"name": "Checagem"}).json()["id"]
            resp = c1.post(f"/api/tasks/{task_id}/run")
            assert resp.status_code == 200
            assert resp.json()["status"] == "completed"
            assert len(c1.get("/api/scheduler/history").json()) == 1

        with TestClient(create_app(scheduler_config(url))) as c2:
            # histórico restaurado
            history = c2.get("/api/scheduler/history").json()
            assert len(history) == 1
            assert history[0]["task_id"] == task_id
            assert history[0]["status"] == "completed"
            # estado de execução restaurado
            task = c2.get(f"/api/tasks/{task_id}").json()
            assert task["run_count"] == 1
            assert task["status"] == "completed"
            assert task["last_run"] is not None

    def test_update_and_delete_survive_restart(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        with TestClient(create_app(scheduler_config(url))) as c1:
            task_id = c1.post("/api/tasks", json={"name": "Original"}).json()["id"]
            # edição via API
            resp = c1.put(f"/api/tasks/{task_id}", json={"name": "Editada", "enabled": False})
            assert resp.status_code == 200
            # outra tarefa é removida
            other_id = c1.post("/api/tasks", json={"name": "Descartavel"}).json()["id"]
            assert c1.delete(f"/api/tasks/{other_id}").status_code == 200

        with TestClient(create_app(scheduler_config(url))) as c2:
            got = c2.get(f"/api/tasks/{task_id}").json()
            assert got["name"] == "Editada"
            assert got["enabled"] is False
            assert c2.get(f"/api/tasks/{other_id}").status_code == 404
            assert len(c2.get("/api/tasks").json()) == 1

    def test_yaml_tasks_are_seeded_and_db_is_authoritative(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        cfg1 = scheduler_config(
            url,
            tasks=[TaskConfig(id="yaml_task", name="Tarefa do YAML", task_type=TaskType.HEALTH_CHECK)],
        )
        with TestClient(create_app(cfg1)) as c1:
            assert any(t["id"] == "yaml_task" for t in c1.get("/api/tasks").json())

        # segundo start sem a task no YAML: o banco é a fonte de verdade
        with TestClient(create_app(scheduler_config(url))) as c2:
            assert any(t["id"] == "yaml_task" for t in c2.get("/api/tasks").json())

    def test_health_and_status_report_database(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        with TestClient(create_app(scheduler_config(url))) as client:
            assert client.get("/health").json()["database"] == "connected"
            status = client.get("/api/scheduler").json()
            assert status["database"] == {"enabled": True, "connected": True}

    def test_disabled_database_reports_disabled(self):
        with TestClient(create_app(SchedulerConfig())) as client:
            assert client.get("/health").json()["database"] == "disabled"
            status = client.get("/api/scheduler").json()
            assert status["database"] == {"enabled": False, "connected": False}
