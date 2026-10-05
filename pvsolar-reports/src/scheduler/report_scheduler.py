"""
Report Scheduler.

Schedules automatic report generation using APScheduler.
"""

from collections.abc import Callable
from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from src.core.config import SchedulerConfig

logger = structlog.get_logger(__name__)


class ReportScheduler:
    """
    Schedules automatic report generation.

    Features:
    - Daily/weekly/monthly scheduling
    - Custom cron expressions
    - Pause/resume
    - Job history
    """

    def __init__(self, config: SchedulerConfig):
        self.config = config
        self._scheduler = AsyncIOScheduler()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._running = False

    async def start(self) -> None:
        if not self.config.enabled:
            logger.info("scheduler.disabled")
            return

        self._scheduler.start()
        self._running = True
        logger.info("scheduler.started")

    async def stop(self) -> None:
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("scheduler.stopped")

    def schedule_daily(self, func: Callable, time_str: str = "06:00", **kwargs: Any) -> str:
        hour, minute = map(int, time_str.split(":"))
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self._scheduler.add_job(func, trigger, **kwargs)
        job_id = f"daily_{time_str}"
        self._jobs[job_id] = {"type": "daily", "time": time_str, "job": job}
        logger.info("scheduler.daily_scheduled", time=time_str)
        return job_id

    def schedule_weekly(self, func: Callable, day: int = 1, time_str: str = "06:00", **kwargs: Any) -> str:
        hour, minute = map(int, time_str.split(":"))
        trigger = CronTrigger(day_of_week=day, hour=hour, minute=minute)
        job = self._scheduler.add_job(func, trigger, **kwargs)
        job_id = f"weekly_{day}_{time_str}"
        self._jobs[job_id] = {"type": "weekly", "day": day, "time": time_str, "job": job}
        logger.info("scheduler.weekly_scheduled", day=day, time=time_str)
        return job_id

    def schedule_monthly(self, func: Callable, day: int = 1, time_str: str = "06:00", **kwargs: Any) -> str:
        hour, minute = map(int, time_str.split(":"))
        trigger = CronTrigger(day=day, hour=hour, minute=minute)
        job = self._scheduler.add_job(func, trigger, **kwargs)
        job_id = f"monthly_{day}_{time_str}"
        self._jobs[job_id] = {"type": "monthly", "day": day, "time": time_str, "job": job}
        logger.info("scheduler.monthly_scheduled", day=day, time=time_str)
        return job_id

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._scheduler.remove_job(job_id)
            del self._jobs[job_id]
            logger.info("scheduler.job_removed", job_id=job_id)
            return True
        return False

    def pause_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._scheduler.pause_job(job_id)
            logger.info("scheduler.job_paused", job_id=job_id)
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._scheduler.resume_job(job_id)
            logger.info("scheduler.job_resumed", job_id=job_id)
            return True
        return False

    def get_jobs(self) -> list[dict[str, Any]]:
        jobs = []
        for job_id, info in self._jobs.items():
            jobs.append({
                "id": job_id,
                "type": info["type"],
                "next_run": str(info["job"].next_run_time) if info["job"].next_run_time else None,
            })
        return jobs
