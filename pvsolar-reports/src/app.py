"""
pvSolar Reports Application.

Main application that initializes and runs the report generation system.
"""

from datetime import UTC, datetime
from pathlib import Path

import structlog
from src.collectors.data_collector import DataCollector
from src.core.config import ReportsConfig, load_config
from src.core.email_sender import EmailSender
from src.generators.excel_generator import ExcelReportGenerator
from src.generators.pdf_generator import PDFReportGenerator
from src.scheduler.report_scheduler import ReportScheduler

logger = structlog.get_logger(__name__)


class PVSolarReports:
    """
    pvSolar Reports Application.

    Main application class that initializes and manages:
    - Data collection from Gateway/Analytics
    - PDF/Excel report generation
    - Email notifications
    - Scheduled reports
    """

    def __init__(self, config: ReportsConfig | None = None, config_path: str | None = None):
        if config:
            self.config = config
        else:
            self.config = load_config(config_path)

        self.collector = DataCollector(self.config.gateway, self.config.analytics)
        self.pdf_generator = PDFReportGenerator(
            company_name=self.config.template.company_name,
            primary_color=self.config.template.primary_color,
            secondary_color=self.config.template.secondary_color,
            logo_path=self.config.template.company_logo,
        )
        self.excel_generator = ExcelReportGenerator(
            company_name=self.config.template.company_name,
            primary_color=self.config.template.primary_color,
        )
        self.email_sender = EmailSender(self.config.email)
        self.scheduler = ReportScheduler(self.config.scheduler)
        self._running = False

    async def start(self) -> None:
        logger.info("app.starting")
        await self.collector.start()
        await self.scheduler.start()
        self._setup_schedule()
        self._running = True
        logger.info("app.started")

    async def stop(self) -> None:
        logger.info("app.stopping")
        await self.scheduler.stop()
        await self.collector.stop()
        self._running = False
        logger.info("app.stopped")

    def _setup_schedule(self) -> None:
        if self.config.scheduler.enabled:
            self.scheduler.schedule_daily(
                self.generate_daily_report,
                time_str=self.config.scheduler.daily_time,
            )
            self.scheduler.schedule_weekly(
                self.generate_weekly_report,
                day=self.config.scheduler.weekly_day,
                time_str=self.config.scheduler.daily_time,
            )
            self.scheduler.schedule_monthly(
                self.generate_monthly_report,
                day=self.config.scheduler.monthly_day,
                time_str=self.config.scheduler.daily_time,
            )

    def _output_path(self, report_type: str, fmt: str, date_str: str) -> str:
        base = self.config.output.pdf_dir if fmt == "pdf" else self.config.output.excel_dir
        return str(Path(base) / f"{report_type}_{date_str}.{fmt}")

    async def generate_daily_report(self, date: datetime | None = None) -> dict:
        target = date or datetime.now(UTC)
        date_str = target.strftime("%Y-%m-%d")
        logger.info("app.generating_daily", date=date_str)

        data = await self.collector.collect_daily_data(target)
        data["plant_name"] = self.config.plant.name

        results = {"date": date_str, "files": []}

        for fmt in self.config.formats:
            path = self._output_path("daily", fmt.value, date_str)
            if fmt.value == "pdf":
                self.pdf_generator.generate_daily_report(data, path)
            elif fmt.value == "excel":
                self.excel_generator.generate_daily_report(data, path)
            results["files"].append(path)

        if self.config.email.enabled:
            await self.email_sender.send_async(
                subject=f"Daily Report - {self.config.plant.name} - {date_str}",
                body=f"Daily report for {date_str} is attached.",
                attachments=results["files"],
            )

        logger.info("app.daily_done", files=results["files"])
        return results

    async def generate_weekly_report(self, end_date: datetime | None = None) -> dict:
        target = end_date or datetime.now(UTC)
        date_str = target.strftime("%Y-%m-%d")
        logger.info("app.generating_weekly", end_date=date_str)

        data = await self.collector.collect_weekly_data(target)

        results = {"period": data.get("period", ""), "files": []}

        for fmt in self.config.formats:
            path = self._output_path("weekly", fmt.value, date_str)
            if fmt.value == "pdf":
                self.pdf_generator.generate_weekly_report(data, path)
            elif fmt.value == "excel":
                self.excel_generator.generate_weekly_report(data, path)
            results["files"].append(path)

        if self.config.email.enabled:
            await self.email_sender.send_async(
                subject=f"Weekly Report - {self.config.plant.name}",
                body="Weekly report is attached.",
                attachments=results["files"],
            )

        logger.info("app.weekly_done", files=results["files"])
        return results

    async def generate_monthly_report(self, year: int | None = None, month: int | None = None) -> dict:
        now = datetime.now(UTC)
        y = year or now.year
        m = month or now.month
        date_str = f"{y}-{m:02d}"
        logger.info("app.generating_monthly", period=date_str)

        data = await self.collector.collect_monthly_data(y, m)

        results = {"period": date_str, "files": []}

        for fmt in self.config.formats:
            path = self._output_path("monthly", fmt.value, date_str)
            if fmt.value == "pdf":
                self.pdf_generator.generate_monthly_report(data, path)
            elif fmt.value == "excel":
                self.excel_generator.generate_monthly_report(data, path)
            results["files"].append(path)

        if self.config.email.enabled:
            await self.email_sender.send_async(
                subject=f"Monthly Report - {self.config.plant.name} - {date_str}",
                body=f"Monthly report for {date_str} is attached.",
                attachments=results["files"],
            )

        logger.info("app.monthly_done", files=results["files"])
        return results

    async def generate_maintenance_report(self) -> dict:
        logger.info("app.generating_maintenance")

        maintenance = await self.collector.get_maintenance()
        data = {"maintenance": maintenance.to_dict() if maintenance else {}}

        results = {"files": []}
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")

        for fmt in self.config.formats:
            path = self._output_path("maintenance", fmt.value, date_str)
            if fmt.value == "pdf":
                self.pdf_generator.generate_maintenance_report(data, path)
            elif fmt.value == "excel":
                self.excel_generator.generate_maintenance_report(data, path)
            results["files"].append(path)

        logger.info("app.maintenance_done", files=results["files"])
        return results

    @property
    def is_running(self) -> bool:
        return self._running
