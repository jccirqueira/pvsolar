import os
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TaskType(StrEnum):
    DATA_SYNC = "data_sync"
    REPORT_GENERATE = "report_generate"
    BACKUP_RUN = "backup_run"
    ALERT_CHECK = "alert_check"
    ANALYTICS_RUN = "analytics_run"
    HEALTH_CHECK = "health_check"
    NOTIFICATION_SEND = "notification_send"
    CUSTOM = "custom"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ScheduleType(StrEnum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TaskPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskConfig(BaseModel):
    id: str = ""
    name: str = ""
    task_type: TaskType = TaskType.CUSTOM
    description: str = ""
    enabled: bool = True
    priority: TaskPriority = TaskPriority.NORMAL
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    interval_seconds: int = Field(default=3600, ge=1)
    cron_expression: str = ""
    time: str = "02:00"
    day_of_week: int = 0
    day_of_month: int = 1
    target_service: str = ""
    target_url: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=3, ge=0)
    retry_delay_seconds: int = Field(default=60, ge=1)
    depends_on: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8009
    title: str = "pvSolar Scheduler API"


class DatabaseConfig(BaseModel):
    """Persistência das tarefas e do histórico (PostgreSQL).

    Quando ``enabled`` é falso o serviço roda somente em memória (comportamento
    original). Definir ``PVSOLAR_DATABASE_URL`` ativa a persistência.
    """
    enabled: bool = False
    url: str = ""  # postgresql+asyncpg://user:senha@host:5432/pvsolar_scheduler
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    create_tables: bool = True
    hydrate_on_startup: bool = True


class SchedulerConfig(BaseModel):
    max_concurrent_tasks: int = Field(default=5, ge=1)
    task_history_max: int = Field(default=1000, ge=10)
    check_interval_seconds: int = Field(default=10, ge=1)
    # Inicia o loop de execucao automaticamente ao subir o servico.
    # Com false, as tarefas so rodam via POST /api/scheduler/start.
    auto_start: bool = True
    api: APIConfig = Field(default_factory=APIConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    tasks: list[TaskConfig] = Field(default_factory=list)
    company_name: str = "pvSolar Scheduler"
    debug: bool = False


def _apply_env_overrides(config: SchedulerConfig) -> SchedulerConfig:
    """Sobrepõe a configuração com variáveis de ambiente (12-factor).

    ``PVSOLAR_DATABASE_URL`` ao ser definida ativa a persistência
    automaticamente; ``PVSOLAR_DB_ENABLED`` força o flag.
    """
    import os

    url = os.environ.get("PVSOLAR_DATABASE_URL", "").strip()
    if url:
        config.database.url = url
        config.database.enabled = True

    enabled = os.environ.get("PVSOLAR_DB_ENABLED")
    if enabled is not None:
        config.database.enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}

    return config


def _default_config_path() -> str | None:
    """Caminho padrão do arquivo de configuração, quando não informado.

    Precedência:
      1. Variável de ambiente ``PVSOLAR_CONFIG`` (caminho arbitrário)
      2. ``config/scheduler.yaml`` na raiz do projeto (copiado do example)

    Retorna ``None`` quando não há arquivo, sinalizando "usar padrões".
    """
    env = os.environ.get("PVSOLAR_CONFIG", "").strip()
    if env:
        return env
    candidate = Path(__file__).resolve().parents[2] / "config" / "scheduler.yaml"
    return str(candidate) if candidate.exists() else None


def load_config(path: str | None = None) -> SchedulerConfig:
    """Carrega config do arquivo YAML ou retorna padrão.

    Sem caminho explícito, procura ``PVSOLAR_CONFIG`` e depois
    ``config/scheduler.yaml``. Em qualquer caso, as variáveis de ambiente
    (ex.: ``PVSOLAR_DATABASE_URL``) têm prioridade sobre o arquivo.
    """
    if path is None:
        path = _default_config_path()
        if path is None:
            return _apply_env_overrides(SchedulerConfig())
    try:
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return _apply_env_overrides(SchedulerConfig(**data))
    except FileNotFoundError:
        return _apply_env_overrides(SchedulerConfig())
