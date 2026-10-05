from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.config import SchedulerConfig, TaskConfig, TaskType, ScheduleType, TaskPriority, load_config
from src.db.service import PersistenceService
from src.tasks.task import TaskRegistry
from src.engine.scheduler import SchedulerEngine

logger = structlog.get_logger()


class CreateTaskRequest(BaseModel):
    name: str
    task_type: str = "custom"
    description: str = ""
    enabled: bool = True
    priority: str = "normal"
    schedule_type: str = "interval"
    interval_seconds: int = 3600
    cron_expression: str = ""
    time: str = "02:00"
    day_of_week: int = 0
    day_of_month: int = 1
    target_service: str = ""
    target_url: str = ""
    payload: dict = {}
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: int = 60
    tags: list[str] = []


class UpdateTaskRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    priority: str | None = None
    interval_seconds: int | None = None
    cron_expression: str | None = None
    tags: list[str] | None = None


def create_app(config: SchedulerConfig | None = None) -> FastAPI:
    """Cria a aplicação FastAPI."""
    if config is None:
        config = load_config()

    registry = TaskRegistry()

    # Camada de persistência: no-op quando database.enabled=false, de modo que
    # os endpoints podem chamá-la incondicionalmente.
    persistence = PersistenceService(config.database)
    engine = SchedulerEngine(config, registry, persistence)

    for task_cfg in config.tasks:
        registry.add_task(task_cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if persistence.enabled:
            # 1) schema + estado do banco (tarefas e histórico) para a memória
            await persistence.startup()
            if config.database.hydrate_on_startup:
                await persistence.hydrate(registry, engine)

        # 2) planeja as próximas execuções (mantém os valores hidratados)
        engine.plan_next_runs()

        if persistence.enabled:
            # 3) tarefas declaradas no YAML que ainda não têm linha no banco
            await persistence.save_all_tasks(registry)
            # 4) aplica a retenção configurada (task_history_max)
            await persistence.prune_history(config.task_history_max)

        # 5) loop de execução (auto_start pode ser desativado no YAML)
        if config.auto_start:
            engine.start()

        yield

        await engine.stop()
        if persistence.enabled:
            await persistence.dispose()

    async def scheduler_status() -> dict:
        """Status do scheduler incluindo o estado da persistência."""
        status = engine.get_status()
        status["database"] = {
            "enabled": persistence.enabled,
            "connected": await persistence.ping(),
        }
        return status

    app = FastAPI(title=config.api.title, version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    async def health():
        db_state = "disabled"
        if persistence.enabled:
            db_state = "connected" if await persistence.ping() else "unavailable"
        return {"status": "healthy", "service": "pvsolar-scheduler", "database": db_state}

    @app.post("/api/tasks")
    async def create_task(req: CreateTaskRequest):
        task_cfg = TaskConfig(
            name=req.name,
            task_type=TaskType(req.task_type),
            description=req.description,
            enabled=req.enabled,
            priority=TaskPriority(req.priority),
            schedule_type=ScheduleType(req.schedule_type),
            interval_seconds=req.interval_seconds,
            cron_expression=req.cron_expression,
            time=req.time,
            day_of_week=req.day_of_week,
            day_of_month=req.day_of_month,
            target_service=req.target_service,
            target_url=req.target_url,
            payload=req.payload,
            timeout_seconds=req.timeout_seconds,
            max_retries=req.max_retries,
            retry_delay_seconds=req.retry_delay_seconds,
            tags=req.tags,
        )
        task = registry.add_task(task_cfg)

        # Write-through: se o banco falhar, desfaz o registro em memória para
        # não haver divergência entre o cache e a fonte de verdade.
        try:
            await persistence.save_task(task)
        except Exception as exc:
            registry.remove_task(task.config.id)
            logger.error("task.persist_failed", task_id=task.config.id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao gravar tarefa no banco")
        return task.to_dict()

    @app.get("/api/tasks")
    async def list_tasks():
        return [t.to_dict() for t in registry.list_tasks()]

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        task = registry.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.to_dict()

    @app.put("/api/tasks/{task_id}")
    async def update_task(task_id: str, req: UpdateTaskRequest):
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        task = registry.update_task(task_id, **updates)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        try:
            await persistence.save_task(task)
        except Exception as exc:
            logger.error("task.persist_failed", task_id=task_id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao gravar tarefa no banco")
        return task.to_dict()

    @app.delete("/api/tasks/{task_id}")
    async def delete_task(task_id: str):
        if registry.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="Task not found")
        # Banco primeiro: se falhar, a memória permanece intacta.
        try:
            await persistence.delete_task(task_id)
        except Exception as exc:
            logger.error("task.persist_failed", task_id=task_id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao remover tarefa do banco")
        registry.remove_task(task_id)
        return {"deleted": task_id}

    @app.post("/api/tasks/{task_id}/run")
    async def run_task(task_id: str):
        # O engine persiste o resultado e o novo estado da tarefa.
        result = await engine.run_task(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")
        return result.to_dict()

    @app.get("/api/scheduler")
    async def get_scheduler_status():
        return await scheduler_status()

    @app.post("/api/scheduler/start")
    async def start_scheduler():
        """Inicia o loop de execução (idempotente)."""
        started = engine.start()
        return {**await scheduler_status(), "started": started}

    @app.post("/api/scheduler/stop")
    async def stop_scheduler():
        """Para o loop de execução (idempotente)."""
        stopped = await engine.stop()
        return {**await scheduler_status(), "stopped": stopped}

    @app.get("/api/scheduler/history")
    async def get_history(task_id: str | None = None, limit: int = 50):
        return engine.get_history(task_id, limit)

    @app.get("/api/statistics")
    async def get_statistics():
        return registry.get_statistics()

    return app


# Instância padrão para uvicorn src.api.app:app
app = create_app()
