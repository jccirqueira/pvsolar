import pytest
from src.core import config as config_module
from src.core.config import (
    SchedulerConfig, TaskConfig, APIConfig,
    TaskType, TaskStatus, ScheduleType, TaskPriority,
    load_config,
)


class TestEnums:
    def test_task_type(self):
        assert TaskType.DATA_SYNC == "data_sync"
        assert TaskType.REPORT_GENERATE == "report_generate"
        assert TaskType.BACKUP_RUN == "backup_run"
        assert TaskType.HEALTH_CHECK == "health_check"
        assert TaskType.CUSTOM == "custom"

    def test_task_status(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
        assert TaskStatus.PAUSED == "paused"

    def test_schedule_type(self):
        assert ScheduleType.ONCE == "once"
        assert ScheduleType.INTERVAL == "interval"
        assert ScheduleType.CRON == "cron"
        assert ScheduleType.DAILY == "daily"
        assert ScheduleType.WEEKLY == "weekly"
        assert ScheduleType.MONTHLY == "monthly"

    def test_task_priority(self):
        assert TaskPriority.LOW == "low"
        assert TaskPriority.NORMAL == "normal"
        assert TaskPriority.HIGH == "high"
        assert TaskPriority.CRITICAL == "critical"


class TestTaskConfig:
    def test_defaults(self):
        c = TaskConfig()
        assert c.enabled is True
        assert c.priority == TaskPriority.NORMAL
        assert c.schedule_type == ScheduleType.INTERVAL
        assert c.interval_seconds == 3600
        assert c.max_retries == 3
        assert c.timeout_seconds == 300

    def test_custom(self):
        c = TaskConfig(name="test", task_type=TaskType.DATA_SYNC, interval_seconds=600)
        assert c.name == "test"
        assert c.task_type == TaskType.DATA_SYNC
        assert c.interval_seconds == 600

    def test_tags(self):
        c = TaskConfig(tags=["daily", "production"])
        assert len(c.tags) == 2


class TestSchedulerConfig:
    def test_defaults(self):
        c = SchedulerConfig()
        assert c.max_concurrent_tasks == 5
        assert c.task_history_max == 1000
        assert c.check_interval_seconds == 10
        assert c.debug is False

    def test_api_config(self):
        c = SchedulerConfig(api=APIConfig(port=9000))
        assert c.api.port == 9000

    def test_with_tasks(self):
        tasks = [TaskConfig(name="t1"), TaskConfig(name="t2")]
        c = SchedulerConfig(tasks=tasks)
        assert len(c.tasks) == 2


class TestLoadConfig:
    def test_load_default(self, monkeypatch):
        # isola a descoberta automatica (config/scheduler.yaml pode existir)
        monkeypatch.delenv("PVSOLAR_CONFIG", raising=False)
        monkeypatch.setattr(config_module, "_default_config_path", lambda: None)
        c = load_config()
        assert isinstance(c, SchedulerConfig)

    def test_load_nonexistent(self):
        c = load_config("nonexistent.yaml")
        assert isinstance(c, SchedulerConfig)

    # ------------------------------------------------------------------
    # Descoberta automatica (PVSOLAR_CONFIG / config/scheduler.yaml)
    # ------------------------------------------------------------------

    def test_env_config_path(self, tmp_path, monkeypatch):
        config_file = tmp_path / "meu_scheduler.yaml"
        config_file.write_text("max_concurrent_tasks: 9\ndebug: true\n")
        monkeypatch.setenv("PVSOLAR_CONFIG", str(config_file))
        c = load_config()
        assert c.max_concurrent_tasks == 9
        assert c.debug is True

    def test_env_config_missing_falls_back_to_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PVSOLAR_CONFIG", str(tmp_path / "nao_existe.yaml"))
        monkeypatch.setattr(config_module, "_default_config_path", lambda: None)
        c = load_config()
        assert c.max_concurrent_tasks == 5

    def test_env_vars_override_config_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "db.yaml"
        config_file.write_text('database:\n  enabled: false\n  url: ""\n')
        monkeypatch.setenv("PVSOLAR_CONFIG", str(config_file))
        monkeypatch.setenv(
            "PVSOLAR_DATABASE_URL",
            "postgresql+asyncpg://postgres:senha@localhost:5432/pvsolar_scheduler",
        )
        c = load_config()
        assert c.database.enabled is True
        assert c.database.url.endswith("/pvsolar_scheduler")
