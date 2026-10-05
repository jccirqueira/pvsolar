import uuid
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import structlog

from src.core.config import TaskConfig, TaskStatus

logger = structlog.get_logger()


class TaskResult:
    def __init__(self, task_id: str, status: TaskStatus, output: Any = None,
                 error: str = "", duration_seconds: float = 0.0, retries: int = 0):
        self.task_id = task_id
        self.status = status
        self.output = output
        self.error = error
        self.duration_seconds = duration_seconds
        self.retries = retries
        self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
            "retries": self.retries,
            "timestamp": self.timestamp,
        }


class Task:
    def __init__(self, config: TaskConfig):
        self.config = config
        self.status = TaskStatus.PENDING
        self.last_run: str | None = None
        self.next_run: str | None = None
        self.run_count: int = 0
        self.failure_count: int = 0
        self.last_result: TaskResult | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.config.id,
            "name": self.config.name,
            "task_type": self.config.task_type.value,
            "status": self.status.value,
            "enabled": self.config.enabled,
            "priority": self.config.priority.value,
            "schedule_type": self.config.schedule_type.value,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "tags": self.config.tags,
        }


class TaskRegistry:
    def __init__(self):
        self._handlers: dict[str, Callable[..., Coroutine]] = {}
        self._tasks: dict[str, Task] = {}

    def register_handler(self, task_type: str, handler: Callable[..., Coroutine]):
        self._handlers[task_type] = handler

    def get_handler(self, task_type: str) -> Callable[..., Coroutine] | None:
        return self._handlers.get(task_type)

    def add_task(self, config: TaskConfig) -> Task:
        if not config.id:
            config.id = str(uuid.uuid4())[:8]
        task = Task(config)
        self._tasks[config.id] = task
        logger.info("task.registered", task_id=config.id, name=config.name)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def remove_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info("task.removed", task_id=task_id)
            return True
        return False

    def update_task(self, task_id: str, **kwargs) -> Task | None:
        task = self._tasks.get(task_id)
        if not task:
            return None
        for key, value in kwargs.items():
            if hasattr(task.config, key):
                setattr(task.config, key, value)
        return task

    def get_statistics(self) -> dict:
        tasks = self.list_tasks()
        return {
            "total": len(tasks),
            "enabled": sum(1 for t in tasks if t.config.enabled),
            "disabled": sum(1 for t in tasks if not t.config.enabled),
            "running": sum(1 for t in tasks if t.status == TaskStatus.RUNNING),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
        }
