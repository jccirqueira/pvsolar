import asyncio
import contextlib
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from croniter import croniter

from src.core.config import SchedulerConfig, ScheduleType, TaskStatus
from src.tasks.task import Task, TaskRegistry, TaskResult

if TYPE_CHECKING:
    from src.db.service import PersistenceService

logger = structlog.get_logger()

# Data distante usada como "nunca mais" para tarefas do tipo ``once``
# apos sua unica execucao.
_NEVER = datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC)


class SchedulerEngine:
    def __init__(
        self,
        config: SchedulerConfig,
        registry: TaskRegistry,
        persistence: "PersistenceService | None" = None,
    ):
        self.config = config
        self.registry = registry
        # Camada opcional de persistência (write-through); None = só memória.
        self.persistence: PersistenceService | None = persistence
        self._running = False
        self._task: asyncio.Task | None = None
        self.history: list[TaskResult] = []

    def _calculate_next_run(self, task: Task) -> str:
        now = datetime.now(UTC)
        cfg = task.config
        st = cfg.schedule_type

        if st == ScheduleType.ONCE:
            # Executa uma unica vez: vence no horario configurado (ou ja,
            # se ele tiver passado hoje) e nunca mais apos a execucao.
            if task.run_count > 0 or task.failure_count > 0:
                return _NEVER.isoformat()
            if cfg.time:
                hour, minute = map(int, cfg.time.split(":"))
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                target = now
            return target.isoformat()
        elif st == ScheduleType.INTERVAL:
            # Intervalo fixo: agora + interval_seconds. Antes este ramo
            # retornava o proprio "agora", fazendo a tarefa vencer a cada
            # tick do loop (bug latente enquanto o loop nao era iniciado).
            return (now + timedelta(seconds=cfg.interval_seconds)).isoformat()
        elif st == ScheduleType.CRON and cfg.cron_expression:
            cron = croniter(cfg.cron_expression, now)
            return cron.get_next(datetime).isoformat()
        elif st == ScheduleType.DAILY:
            hour, minute = map(int, cfg.time.split(":"))
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_dt <= now:
                next_dt += timedelta(days=1)
            return next_dt.isoformat()
        elif st == ScheduleType.WEEKLY:
            hour, minute = map(int, cfg.time.split(":"))
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            days_ahead = cfg.day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_dt += timedelta(days=days_ahead)
            return next_dt.isoformat()
        elif st == ScheduleType.MONTHLY:
            hour, minute = map(int, cfg.time.split(":"))
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0,
                                  day=cfg.day_of_month)
            if next_dt <= now:
                if next_dt.month == 12:
                    next_dt = next_dt.replace(year=next_dt.year + 1, month=1)
                else:
                    next_dt = next_dt.replace(month=next_dt.month + 1)
            return next_dt.isoformat()
        return now.isoformat()

    def _should_run(self, task: Task) -> bool:
        if not task.config.enabled:
            return False
        if task.next_run is None:
            task.next_run = self._calculate_next_run(task)
        now = datetime.now(UTC)
        next_dt = datetime.fromisoformat(task.next_run)
        return now >= next_dt

    async def _execute_task(self, task: Task) -> TaskResult:
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now(UTC).isoformat()
        logger.info("task.executing", task_id=task.config.id, name=task.config.name)

        start = time.time()
        retries = 0
        last_error = ""

        handler = self.registry.get_handler(task.config.task_type.value)

        while retries <= task.config.max_retries:
            try:
                if handler:
                    output = await asyncio.wait_for(
                        handler(task.config),
                        timeout=task.config.timeout_seconds
                    )
                else:
                    output = {"message": f"Task {task.config.name} executed (no handler)"}

                duration = time.time() - start
                result = TaskResult(task.config.id, TaskStatus.COMPLETED, output, duration_seconds=duration, retries=retries)
                task.status = TaskStatus.COMPLETED
                task.run_count += 1
                task.last_result = result
                task.next_run = self._calculate_next_run(task)
                logger.info("task.completed", task_id=task.config.id, duration=duration)
                return result

            except Exception as e:
                last_error = str(e)
                retries += 1
                if retries <= task.config.max_retries:
                    logger.warning("task.retry", task_id=task.config.id, retry=retries, error=last_error)
                    await asyncio.sleep(min(task.config.retry_delay_seconds, 5))

        duration = time.time() - start
        result = TaskResult(task.config.id, TaskStatus.FAILED, error=last_error, duration_seconds=duration, retries=retries - 1)
        task.status = TaskStatus.FAILED
        task.failure_count += 1
        task.last_result = result
        task.next_run = self._calculate_next_run(task)
        logger.error("task.failed", task_id=task.config.id, error=last_error)
        return result

    async def run_task(self, task_id: str) -> TaskResult | None:
        task = self.registry.get_task(task_id)
        if not task:
            return None
        result = await self._execute_task(task)
        await self._add_history(result)
        return result

    async def run_all_due(self) -> list[TaskResult]:
        results = []
        for task in self.registry.list_tasks():
            if self._should_run(task) and task.status != TaskStatus.RUNNING:
                result = await self._execute_task(task)
                await self._add_history(result)
                results.append(result)
        return results

    async def _add_history(self, result: TaskResult):
        self.history.append(result)
        if len(self.history) > self.config.task_history_max:
            self.history = self.history[-self.config.task_history_max:]

        # Write-through: grava a execução e o novo estado da tarefa
        # (run_count, status, next_run, ...) para sobreviver a reinícios.
        if self.persistence is not None and self.persistence.enabled:
            try:
                await self.persistence.save_result(result)
                task = self.registry.get_task(result.task_id)
                if task is not None:
                    await self.persistence.save_task(task)
            except Exception as exc:
                # A execução já concluiu; falha de I/O não pode rebaixar
                # a execução a erro HTTP — apenas é registrada.
                logger.error(
                    "task.persist_failed",
                    task_id=result.task_id,
                    error=str(exc),
                )

    def plan_next_runs(self) -> None:
        """Preenche ``next_run`` das tarefas que ainda não têm agendamento.

        Preserva o valor hidratado do banco (o banco é a fonte de verdade
        para tarefas que já possuem linha).
        """
        for task in self.registry.list_tasks():
            if task.next_run is None:
                task.next_run = self._calculate_next_run(task)

    def start(self) -> bool:
        """Inicia o loop de execução em background (idempotente).

        Retorna ``True`` quando o loop foi de fato iniciado. Deve ser chamado
        dentro de um event loop ativo (lifespan ou endpoint HTTP).
        """
        if self._running:
            return False
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("scheduler.started", tasks=len(self.registry.list_tasks()))
        return True

    async def stop(self) -> bool:
        """Para o loop de execução (idempotente).

        Aguarda a tarefa terminar, de modo que ``running`` nunca fique
        preso em ``True`` após a parada.
        """
        if not self._running and self._task is None:
            return False
        self._running = False
        task, self._task = self._task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        logger.info("scheduler.stopped")
        return True

    async def _loop(self) -> None:
        try:
            while self._running:
                await self.run_all_due()
                await asyncio.sleep(self.config.check_interval_seconds)
        finally:
            # Cobertura para cancelamento/erro: o status nunca fica preso.
            self._running = False

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "auto_start": self.config.auto_start,
            "total_tasks": len(self.registry.list_tasks()),
            "history_count": len(self.history),
        }

    def get_history(self, task_id: str | None = None, limit: int = 50) -> list[dict]:
        if task_id:
            return [r.to_dict() for r in self.history if r.task_id == task_id][-limit:]
        return [r.to_dict() for r in self.history][-limit:]
