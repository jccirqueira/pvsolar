import asyncio
import calendar
from datetime import datetime, timedelta, timezone

import structlog
from croniter import croniter

from src.core.config import BackupConfig, ScheduleFrequency
from src.backup.engine import BackupEngine

logger = structlog.get_logger()


class BackupScheduler:
    def __init__(self, config: BackupConfig, backup_engine: BackupEngine):
        self.config = config
        self.backup_engine = backup_engine
        self._running = False
        self._task: asyncio.Task | None = None
        self.last_run: str | None = None
        self.next_run: str | None = None

    def _calculate_next_run(self) -> str:
        now = datetime.now(timezone.utc)
        freq = self.config.schedule.frequency

        if freq == ScheduleFrequency.CUSTOM and self.config.schedule.cron_expression:
            cron = croniter(self.config.schedule.cron_expression, now)
            return cron.get_next(datetime).isoformat()

        hour, minute = map(int, self.config.schedule.time.split(":"))

        if freq == ScheduleFrequency.HOURLY:
            next_dt = now.replace(minute=minute, second=0, microsecond=0)
            if next_dt <= now:
                # timedelta rola o dia/mes/ano corretamente (23:XX -> 00:XX)
                next_dt += timedelta(hours=1)
        elif freq == ScheduleFrequency.DAILY:
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_dt <= now:
                next_dt += timedelta(days=1)
        elif freq == ScheduleFrequency.WEEKLY:
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            days_ahead = self.config.schedule.day_of_week - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_dt += timedelta(days=days_ahead)
        elif freq == ScheduleFrequency.MONTHLY:
            # Clamp do dia para o tamanho real do mes (ex.: 31 em fevereiro)
            day = min(self.config.schedule.day_of_month,
                      calendar.monthrange(now.year, now.month)[1])
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0,
                                  day=day)
            if next_dt <= now:
                if next_dt.month == 12:
                    year, month = next_dt.year + 1, 1
                else:
                    year, month = next_dt.year, next_dt.month + 1
                day = min(self.config.schedule.day_of_month,
                          calendar.monthrange(year, month)[1])
                next_dt = next_dt.replace(year=year, month=month, day=day)
        else:
            next_dt = now

        return next_dt.isoformat()

    def should_run(self) -> bool:
        if not self.config.schedule.enabled:
            return False
        now = datetime.now(timezone.utc)
        if self.next_run is None:
            self.next_run = self._calculate_next_run()
        next_dt = datetime.fromisoformat(self.next_run)
        return now >= next_dt

    async def _run_backup(self):
        logger.info("scheduler.running_backup")
        self.last_run = datetime.now(timezone.utc).isoformat()
        self.next_run = self._calculate_next_run()
        await self.backup_engine.create_backup()
        logger.info("scheduler.backup_complete", next_run=self.next_run)

    async def start(self):
        self._running = True
        self.next_run = self._calculate_next_run()
        logger.info("scheduler.started", next_run=self.next_run)

        while self._running:
            if self.should_run():
                await self._run_backup()
            await asyncio.sleep(60)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("scheduler.stopped")

    def get_status(self) -> dict:
        return {
            "enabled": self.config.schedule.enabled,
            "frequency": self.config.schedule.frequency.value,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "running": self._running,
        }

    async def run_now(self) -> dict:
        await self._run_backup()
        return {"status": "completed", "next_run": self.next_run}
