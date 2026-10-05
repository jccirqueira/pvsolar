import pytest
from src.backup.engine import BackupEngine
from src.core.config import BackupConfig, ScheduleFrequency
from src.scheduler.scheduler import BackupScheduler


@pytest.fixture
def config():
    return BackupConfig(schedule={"enabled": True, "frequency": "daily", "time": "02:00"})


@pytest.fixture
def engine(config):
    return BackupEngine(config)


class TestBackupScheduler:
    def test_create_scheduler(self, config, engine):
        scheduler = BackupScheduler(config, engine)
        assert scheduler is not None

    def test_calculate_next_run(self, config, engine):
        scheduler = BackupScheduler(config, engine)
        next_run = scheduler._calculate_next_run()
        assert next_run is not None
        assert "T" in next_run

    def test_should_run_disabled(self, config, engine):
        config.schedule.enabled = False
        scheduler = BackupScheduler(config, engine)
        assert scheduler.should_run() is False

    def test_get_status(self, config, engine):
        scheduler = BackupScheduler(config, engine)
        status = scheduler.get_status()
        assert status["enabled"] is True
        assert status["frequency"] == "daily"

    def test_next_run_hourly(self, engine):
        from src.core.config import BackupConfig
        config = BackupConfig(schedule={"frequency": "hourly"})
        scheduler = BackupScheduler(config, engine)
        next_run = scheduler._calculate_next_run()
        assert next_run is not None

    def test_next_run_weekly(self, engine):
        from src.core.config import BackupConfig
        config = BackupConfig(schedule={"frequency": "weekly", "day_of_week": 1})
        scheduler = BackupScheduler(config, engine)
        next_run = scheduler._calculate_next_run()
        assert next_run is not None

    def test_next_run_monthly(self, engine):
        from src.core.config import BackupConfig
        config = BackupConfig(schedule={"frequency": "monthly", "day_of_month": 15})
        scheduler = BackupScheduler(config, engine)
        next_run = scheduler._calculate_next_run()
        assert next_run is not None

    def test_next_run_custom_cron(self, engine):
        from src.core.config import BackupConfig
        config = BackupConfig(schedule={"frequency": "custom", "cron_expression": "0 */6 * * *"})
        scheduler = BackupScheduler(config, engine)
        next_run = scheduler._calculate_next_run()
        assert next_run is not None

    def test_run_now(self, config, engine):
        scheduler = BackupScheduler(config, engine)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(scheduler.run_now())
        assert result["status"] == "completed"

    def test_next_run_hourly_rollover_at_23h(self, engine, monkeypatch):
        # Regressao: as 23:57 UTC o hourly nao pode calcular "hora 24"
        from datetime import datetime as real_datetime

        import src.scheduler.scheduler as sched_mod

        class _FakeDateTime:
            @classmethod
            def now(cls, tz=None):
                return real_datetime(2026, 1, 1, 23, 57, tzinfo=tz)

        monkeypatch.setattr(sched_mod, "datetime", _FakeDateTime)

        config = BackupConfig(schedule={"frequency": "hourly", "time": "00:30"})
        scheduler = BackupScheduler(config, engine)
        next_dt = real_datetime.fromisoformat(scheduler._calculate_next_run())
        assert next_dt.day == 2
        assert (next_dt.hour, next_dt.minute) == (0, 30)

    def test_next_run_monthly_day_overflow(self, engine, monkeypatch):
        # Regressao: dia 31 nao pode estourar em meses com menos dias
        from datetime import datetime as real_datetime

        import src.scheduler.scheduler as sched_mod

        class _FakeDateTime:
            @classmethod
            def now(cls, tz=None):
                return real_datetime(2026, 1, 31, 10, 0, tzinfo=tz)

        monkeypatch.setattr(sched_mod, "datetime", _FakeDateTime)

        config = BackupConfig(
            schedule={"frequency": "monthly", "day_of_month": 31, "time": "02:00"}
        )
        scheduler = BackupScheduler(config, engine)
        next_dt = real_datetime.fromisoformat(scheduler._calculate_next_run())
        # 02:00 de 31/01 ja passou -> proxima execucao: 28/02/2026 (clamp)
        assert (next_dt.year, next_dt.month, next_dt.day) == (2026, 2, 28)
        assert (next_dt.hour, next_dt.minute) == (2, 0)
