from datetime import datetime, timezone

import pytest
from src.core.config import SchedulerConfig, TaskConfig, ScheduleType, TaskType, TaskStatus
from src.tasks.task import TaskRegistry
from src.engine.scheduler import SchedulerEngine


@pytest.fixture
def config():
    return SchedulerConfig(check_interval_seconds=1)


@pytest.fixture
def registry():
    return TaskRegistry()


@pytest.fixture
def engine(config, registry):
    return SchedulerEngine(config, registry)


class TestSchedulerEngine:
    def test_create(self, engine):
        assert engine is not None

    def test_calculate_next_run_interval(self, engine, registry):
        task = registry.add_task(TaskConfig(id="t1", schedule_type=ScheduleType.INTERVAL, interval_seconds=300))
        next_run = engine._calculate_next_run(task)
        assert next_run is not None
        # deve vencer daqui a ~300s (e nao "agora")
        delta = (datetime.fromisoformat(next_run) - datetime.now(timezone.utc)).total_seconds()
        assert 290 <= delta <= 310

    def test_calculate_next_run_once_before_executing(self, engine, registry):
        # horario ja passou no dia => vence imediatamente
        task = registry.add_task(TaskConfig(id="t1", schedule_type=ScheduleType.ONCE, time="00:00"))
        next_run = engine._calculate_next_run(task)
        assert datetime.fromisoformat(next_run) <= datetime.now(timezone.utc)

    def test_calculate_next_run_once_never_again_after_run(self, engine, registry):
        task = registry.add_task(TaskConfig(id="t1", schedule_type=ScheduleType.ONCE, time="00:00"))
        task.run_count = 1
        next_run = engine._calculate_next_run(task)
        assert datetime.fromisoformat(next_run).year == 9999

    def test_calculate_next_run_daily(self, engine, registry):
        task = registry.add_task(TaskConfig(id="t1", schedule_type=ScheduleType.DAILY, time="14:30"))
        next_run = engine._calculate_next_run(task)
        assert "T" in next_run

    def test_calculate_next_run_weekly(self, engine, registry):
        task = registry.add_task(TaskConfig(id="t1", schedule_type=ScheduleType.WEEKLY, day_of_week=1, time="09:00"))
        next_run = engine._calculate_next_run(task)
        assert next_run is not None

    def test_calculate_next_run_monthly(self, engine, registry):
        task = registry.add_task(TaskConfig(id="t1", schedule_type=ScheduleType.MONTHLY, day_of_month=15))
        next_run = engine._calculate_next_run(task)
        assert next_run is not None

    def test_calculate_next_run_cron(self, engine, registry):
        task = registry.add_task(TaskConfig(id="t1", schedule_type=ScheduleType.CRON, cron_expression="0 */6 * * *"))
        next_run = engine._calculate_next_run(task)
        assert next_run is not None

    def test_should_run_disabled(self, engine, registry):
        task = registry.add_task(TaskConfig(id="t1", enabled=False))
        assert engine._should_run(task) is False

    def test_run_task(self, engine, registry):
        async def handler(cfg):
            return {"result": "ok"}
        registry.register_handler("custom", handler)
        registry.add_task(TaskConfig(id="t1", name="Test"))
        import asyncio
        result = asyncio.run(engine.run_task("t1"))
        assert result is not None
        assert result.status == TaskStatus.COMPLETED

    def test_run_nonexistent(self, engine):
        import asyncio
        result = asyncio.run(engine.run_task("nope"))
        assert result is None

    def test_run_task_failure(self, engine, registry):
        async def handler(cfg):
            raise ValueError("test error")
        registry.register_handler("custom", handler)
        registry.add_task(TaskConfig(id="t1", name="Fail", max_retries=0))
        import asyncio
        result = asyncio.run(engine.run_task("t1"))
        assert result.status == TaskStatus.FAILED
        assert "test error" in result.error

    def test_get_status(self, engine, registry):
        registry.add_task(TaskConfig(id="t1"))
        status = engine.get_status()
        assert status["total_tasks"] == 1

    def test_get_history(self, engine, registry):
        async def handler(cfg):
            return {"ok": True}
        registry.register_handler("custom", handler)
        registry.add_task(TaskConfig(id="t1"))
        import asyncio
        asyncio.run(engine.run_task("t1"))
        history = engine.get_history()
        assert len(history) >= 1

    def test_get_history_by_task(self, engine, registry):
        async def handler(cfg):
            return {"ok": True}
        registry.register_handler("custom", handler)
        registry.add_task(TaskConfig(id="t1"))
        registry.add_task(TaskConfig(id="t2"))
        import asyncio
        asyncio.run(engine.run_task("t1"))
        asyncio.run(engine.run_task("t2"))
        history = engine.get_history(task_id="t1")
        assert all(h["task_id"] == "t1" for h in history)
