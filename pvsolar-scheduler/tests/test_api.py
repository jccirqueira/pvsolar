"""Testes da API do pvSolar Scheduler: ciclo de vida do loop de execução.

Cobre o ``auto_start`` e os endpoints de controle (start/stop) do scheduler,
incluindo a execução automática de tarefas vencidas.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.config import SchedulerConfig, TaskConfig


class TestSchedulerControl:
    def test_auto_start_keeps_loop_running(self):
        with TestClient(create_app(SchedulerConfig())) as client:
            status = client.get("/api/scheduler").json()
            assert status["running"] is True
            assert status["auto_start"] is True

    def test_auto_start_disabled_starts_in_manual_mode(self):
        with TestClient(create_app(SchedulerConfig(auto_start=False))) as client:
            status = client.get("/api/scheduler").json()
            assert status["running"] is False
            assert status["auto_start"] is False

    def test_start_and_stop_are_idempotent(self):
        with TestClient(create_app(SchedulerConfig(auto_start=False))) as client:
            # iniciar
            started = client.post("/api/scheduler/start").json()
            assert started["running"] is True
            assert started["started"] is True

            # iniciar de novo: já rodando
            again = client.post("/api/scheduler/start").json()
            assert again["running"] is True
            assert again["started"] is False

            # parar
            stopped = client.post("/api/scheduler/stop").json()
            assert stopped["running"] is False
            assert stopped["stopped"] is True

            # parar de novo: já parado
            already = client.post("/api/scheduler/stop").json()
            assert already["running"] is False
            assert already["stopped"] is False

            # o status reflete o estado final
            assert client.get("/api/scheduler").json()["running"] is False

    def test_loop_executes_due_tasks_automatically(self):
        cfg = SchedulerConfig(
            check_interval_seconds=1,
            tasks=[TaskConfig(id="tick", name="Tick", interval_seconds=1)],
        )
        with TestClient(create_app(cfg)) as client:
            assert client.get("/api/scheduler").json()["running"] is True

            # a tarefa vence a cada 1s e o loop verifica a cada 1s
            time.sleep(3)

            task = client.get("/api/tasks/tick").json()
            assert task["run_count"] >= 1
            assert task["status"] == "completed"

            history = client.get("/api/scheduler/history").json()
            assert len(history) >= 1
            assert history[-1]["task_id"] == "tick"
            assert history[-1]["status"] == "completed"

    def test_stopped_loop_does_not_execute_tasks(self):
        cfg = SchedulerConfig(
            check_interval_seconds=1,
            tasks=[TaskConfig(id="tick", name="Tick", interval_seconds=1)],
        )
        with TestClient(create_app(cfg)) as client:
            assert client.post("/api/scheduler/stop").json()["running"] is False
            time.sleep(2)
            task = client.get("/api/tasks/tick").json()
            assert task["run_count"] == 0
