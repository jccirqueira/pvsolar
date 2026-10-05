"""Serviço de persistência do pvSolar Scheduler.

Responsável por:

1. **Startup** — criar o schema e carregar tarefas/histórico do PostgreSQL
   para o ``TaskRegistry`` e para o ``SchedulerEngine``.
2. **Write-through** — gravar cada mutação da API (criar/editar/remover
   tarefa) e cada execução concluída (resultado + estado da tarefa).

O histórico é truncado em ``task_history_max`` (tanto em memória quanto no
banco) para manter o crescimento sob controle.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete, select

from src.core.config import (
    DatabaseConfig,
    ScheduleType,
    TaskConfig,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from src.db.base import Base, create_engine, create_session_factory
from src.db.models import TaskResultRow, TaskRow
from src.tasks.task import Task, TaskRegistry, TaskResult

if TYPE_CHECKING:  # evita import circular com o engine (que recebe o serviço)
    from src.engine.scheduler import SchedulerEngine

logger = structlog.get_logger()


def _as_utc(value: datetime | None) -> datetime | None:
    """Normaliza para datetime aware (SQLite devolve naive, PostgreSQL não)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_iso(value: str | None) -> datetime | None:
    """Converte a ISO string do domínio em datetime (``None`` se vazia)."""
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(value))
    except ValueError:
        logger.warning("task.bad_timestamp", value=value)
        return None


def _json_safe(value):
    """Sanitiza recursivamente para que a saída seja serializável em JSON.

    Handlers podem retornar objetos arbitrários. Em vez de falhar a gravação
    (ou descartar a saída inteira), mantém o que é serializável e substitui
    apenas os objetos problemáticos pela sua representação textual.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return {"_type": type(value).__name__, "_repr": repr(value)}


# ---------------------------------------------------------------------------
# Mapeamento row <-> domínio
# ---------------------------------------------------------------------------

def _apply_task_row(row: TaskRow, task: Task) -> None:
    cfg = task.config
    row.id = cfg.id
    row.name = cfg.name
    row.task_type = cfg.task_type.value
    row.description = cfg.description
    row.enabled = cfg.enabled
    row.priority = cfg.priority.value
    row.schedule_type = cfg.schedule_type.value
    row.interval_seconds = cfg.interval_seconds
    row.cron_expression = cfg.cron_expression
    row.time = cfg.time
    row.day_of_week = cfg.day_of_week
    row.day_of_month = cfg.day_of_month
    row.target_service = cfg.target_service
    row.target_url = cfg.target_url
    row.payload = dict(cfg.payload or {})
    row.timeout_seconds = cfg.timeout_seconds
    row.max_retries = cfg.max_retries
    row.retry_delay_seconds = cfg.retry_delay_seconds
    row.depends_on = list(cfg.depends_on or [])
    row.tags = list(cfg.tags or [])
    row.status = task.status.value
    row.last_run = _parse_iso(task.last_run)
    row.next_run = _parse_iso(task.next_run)
    row.run_count = task.run_count
    row.failure_count = task.failure_count


def _config_from_row(row: TaskRow) -> TaskConfig:
    return TaskConfig(
        id=row.id,
        name=row.name,
        task_type=TaskType(row.task_type),
        description=row.description,
        enabled=row.enabled,
        priority=TaskPriority(row.priority),
        schedule_type=ScheduleType(row.schedule_type),
        interval_seconds=row.interval_seconds,
        cron_expression=row.cron_expression,
        time=row.time,
        day_of_week=row.day_of_week,
        day_of_month=row.day_of_month,
        target_service=row.target_service,
        target_url=row.target_url,
        payload=dict(row.payload or {}),
        timeout_seconds=row.timeout_seconds,
        max_retries=row.max_retries,
        retry_delay_seconds=row.retry_delay_seconds,
        depends_on=list(row.depends_on or []),
        tags=list(row.tags or []),
    )


def _result_from_row(row: TaskResultRow) -> TaskResult:
    result = TaskResult(
        task_id=row.task_id,
        status=TaskStatus(row.status),
        output=row.output,
        error=row.error,
        duration_seconds=row.duration_seconds,
        retries=row.retries,
    )
    ts = _as_utc(row.timestamp)
    if ts is not None:
        result.timestamp = ts.isoformat()
    return result


# ---------------------------------------------------------------------------
# Serviço
# ---------------------------------------------------------------------------

class PersistenceService:
    """Façade de persistência do Scheduler (engine + sessões + hidratação)."""

    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._engine = None
        self._sessions = None

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @property
    def started(self) -> bool:
        return self._sessions is not None

    # -- ciclo de vida ----------------------------------------------------

    async def startup(self) -> None:
        """Cria engine e schema (idempotente). No-op se desativado."""
        if not self.enabled:
            logger.info("database.disabled", reason="database.enabled=false")
            return

        self._engine = create_engine(self.config)
        self._sessions = create_session_factory(self._engine)

        if self.config.create_tables:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        logger.info("database.started", url=_safe_url(self.config.url))

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessions = None
            logger.info("database.disposed")

    async def ping(self) -> bool:
        if not self.enabled or self._sessions is None:
            return False
        try:
            from sqlalchemy import text

            async with self._sessions() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as exc:  # pragma: no cover - depende da infra
            logger.warning("database.ping_failed", error=str(exc))
            return False

    def _require(self):
        if self._sessions is None:
            raise RuntimeError("PersistenceService.startup() nao foi chamado")
        return self._sessions

    # -- hidratação -------------------------------------------------------

    async def hydrate(self, registry: TaskRegistry, engine: SchedulerEngine) -> dict:
        """Carrega tarefas e histórico do banco.

        O banco é a fonte de verdade: uma tarefa existente no banco substitui
        a versão vinda do YAML (mantendo o estado de execução persistido).
        """
        if not self.enabled:
            return {"tasks": 0, "results": 0}

        sessions = self._require()
        async with sessions() as session:
            task_rows = (await session.execute(select(TaskRow))).scalars().all()
            result_rows = (
                await session.execute(
                    select(TaskResultRow)
                    .order_by(TaskResultRow.timestamp.desc(), TaskResultRow.id.desc())
                    .limit(engine.config.task_history_max)
                )
            ).scalars().all()

        for row in task_rows:
            # add_task substitui a versão vinda do YAML (o banco é a fonte
            # de verdade para o estado de execução)
            task = registry.add_task(_config_from_row(row))
            task.status = TaskStatus(row.status)
            ts_last = _as_utc(row.last_run)
            ts_next = _as_utc(row.next_run)
            task.last_run = ts_last.isoformat() if ts_last else None
            task.next_run = ts_next.isoformat() if ts_next else None
            task.run_count = row.run_count or 0
            task.failure_count = row.failure_count or 0

        # mais recente primeiro no banco → ordem cronológica em memória
        engine.history = [_result_from_row(r) for r in reversed(result_rows)]

        stats = {"tasks": len(task_rows), "results": len(result_rows)}
        logger.info("database.hydrated", **stats)
        return stats

    # -- tarefas ----------------------------------------------------------

    async def save_task(self, task: Task) -> None:
        """Insere ou atualiza uma tarefa (configuração + estado)."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            row = await session.get(TaskRow, task.config.id)
            if row is None:
                row = TaskRow(id=task.config.id)
                session.add(row)
            _apply_task_row(row, task)
            await session.commit()
        logger.debug("database.task_saved", task_id=task.config.id, name=task.config.name)

    async def save_all_tasks(self, registry: TaskRegistry) -> int:
        """Persiste todas as tarefas do registro (upsert). Retorna o total."""
        if not self.enabled:
            return 0
        for task in registry.list_tasks():
            await self.save_task(task)
        return len(registry.list_tasks())

    async def delete_task(self, task_id: str) -> None:
        """Remove uma tarefa e seu histórico."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            await session.execute(delete(TaskResultRow).where(TaskResultRow.task_id == task_id))
            await session.execute(delete(TaskRow).where(TaskRow.id == task_id))
            await session.commit()
        logger.debug("database.task_deleted", task_id=task_id)

    # -- histórico --------------------------------------------------------

    async def save_result(self, result: TaskResult) -> None:
        """Grava uma execução no histórico."""
        if not self.enabled:
            return
        sessions = self._require()
        ts = _parse_iso(result.timestamp) or datetime.now(UTC)
        async with sessions() as session:
            session.add(
                TaskResultRow(
                    task_id=result.task_id,
                    status=result.status.value,
                    output=_json_safe(result.output),
                    error=result.error,
                    duration_seconds=result.duration_seconds,
                    retries=result.retries,
                    timestamp=ts,
                )
            )
            await session.commit()

    async def prune_history(self, max_rows: int) -> int:
        """Remove execuções além de ``max_rows`` (retenção configurada)."""
        if not self.enabled:
            return 0
        sessions = self._require()
        async with sessions() as session:
            subquery = (
                select(TaskResultRow.id)
                .order_by(TaskResultRow.timestamp.desc(), TaskResultRow.id.desc())
                .offset(max_rows)
                .scalar_subquery()
            )
            result = await session.execute(
                delete(TaskResultRow).where(TaskResultRow.id.in_(subquery))
            )
            await session.commit()
            deleted = result.rowcount or 0
        if deleted:
            logger.info("database.history_pruned", deleted=deleted, max_rows=max_rows)
        return deleted


def _safe_url(url: str) -> str:
    """Mascara a senha da URL antes de logar."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"
