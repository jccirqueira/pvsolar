"""Modelos ORM do pvSolar Scheduler.

Persiste duas coisas que antes viviam apenas em memória:

* ``tasks``          — cadastro das tarefas (configuração + estado de execução)
* ``task_results``   — histórico de execuções (audit log)

Tipos são portáveis (``String``/``DateTime``/``JSON``): o mesmo schema roda em
PostgreSQL (produção) e SQLite (testes unitários).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskRow(Base):
    """Tarefa agendada: configuração declarativa + estado de execução."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    task_type: Mapped[str] = mapped_column(String(48), default="custom", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")

    # agendamento
    schedule_type: Mapped[str] = mapped_column(String(16), default="interval", index=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    cron_expression: Mapped[str] = mapped_column(String(120), default="")
    time: Mapped[str] = mapped_column(String(8), default="02:00")
    day_of_week: Mapped[int] = mapped_column(Integer, default=0)
    day_of_month: Mapped[int] = mapped_column(Integer, default=1)

    # execução
    target_service: Mapped[str] = mapped_column(String(100), default="")
    target_url: Mapped[str] = mapped_column(String(512), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=60)
    depends_on: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)

    # estado de execução
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class TaskResultRow(Base):
    """Uma execução de tarefa (histórico)."""

    __tablename__ = "task_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    output: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
