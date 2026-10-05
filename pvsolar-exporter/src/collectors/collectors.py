from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from src.core.config import CollectorConfig, ServiceType
from src.core.exporter import CollectorResult, MetricValue

logger = structlog.get_logger()


class BaseCollector:
    def __init__(self, service_type: ServiceType, config: CollectorConfig):
        self.service_type = service_type
        self.config = config
        self.client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        return self.client

    async def collect(self) -> CollectorResult:
        try:
            return await self._do_collect()
        except Exception as e:
            logger.error("collector_error", service=self.service_type.value, error=str(e))
            return CollectorResult(
                service=self.service_type.value,
                success=False,
                error=str(e),
            )

    async def _do_collect(self) -> CollectorResult:
        raise NotImplementedError

    async def _fetch_json(self, path: str) -> dict[str, Any] | None:
        try:
            client = await self._get_client()
            url = f"{self.config.url}{path}"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("fetch_failed", url=url, error=str(e))
            return None

    async def close(self):
        if self.client and not self.client.is_closed:
            await self.client.aclose()


class GatewayCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.GATEWAY, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="inverter_count", value=data.get("inverter_count", 0)),
                MetricValue(name="mqtt_connected", value=1 if data.get("mqtt_connected") else 0),
                MetricValue(name="uptime_seconds", value=data.get("uptime_seconds", 0)),
                MetricValue(name="messages_received", value=data.get("messages_received", 0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class AnalyticsCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.ANALYTICS, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="models_loaded", value=data.get("models_loaded", 0)),
                MetricValue(name="predictions_count", value=data.get("predictions_count", 0)),
                MetricValue(name="anomalies_detected", value=data.get("anomalies_detected", 0)),
                MetricValue(name="accuracy_score", value=data.get("accuracy_score", 0.0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class ScadaCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.SCADA, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="screens_active", value=data.get("screens_active", 0)),
                MetricValue(name="widgets_rendered", value=data.get("widgets_rendered", 0)),
                MetricValue(name="active_users", value=data.get("active_users", 0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class ReportsCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.REPORTS, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="reports_generated", value=data.get("reports_generated", 0)),
                MetricValue(name="pdf_count", value=data.get("pdf_count", 0)),
                MetricValue(name="excel_count", value=data.get("excel_count", 0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class FleetCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.FLEET, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="total_sites", value=data.get("total_sites", 0)),
                MetricValue(name="online_sites", value=data.get("online_sites", 0)),
                MetricValue(name="offline_sites", value=data.get("offline_sites", 0)),
                MetricValue(name="total_capacity_mw", value=data.get("total_capacity_mw", 0.0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class AlertCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.ALERT, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="active_alerts", value=data.get("active_alerts", 0)),
                MetricValue(name="notifications_sent", value=data.get("notifications_sent", 0)),
                MetricValue(name="rules_active", value=data.get("rules_active", 0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class GridCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.GRID, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="compliance_score", value=data.get("compliance_score", 0.0)),
                MetricValue(name="violations_count", value=data.get("violations_count", 0)),
                MetricValue(name="voltage_pu", value=data.get("voltage_pu", 1.0)),
                MetricValue(name="frequency_hz", value=data.get("frequency_hz", 60.0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class TwinCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.TWIN, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="simulations_running", value=data.get("simulations_running", 0)),
                MetricValue(name="total_simulations", value=data.get("total_simulations", 0)),
                MetricValue(name="accuracy_percent", value=data.get("accuracy_percent", 0.0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class AuthCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.AUTH, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="active_users", value=data.get("active_users", 0)),
                MetricValue(name="total_tokens", value=data.get("total_tokens", 0)),
                MetricValue(name="failed_logins", value=data.get("failed_logins", 0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class BackupCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.BACKUP, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="total_backups", value=data.get("total_backups", 0)),
                MetricValue(name="last_backup_status", value=1 if data.get("last_backup_success") else 0),
                MetricValue(name="total_size_bytes", value=data.get("total_size_bytes", 0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


class SchedulerCollector(BaseCollector):
    def __init__(self, config: CollectorConfig):
        super().__init__(ServiceType.SCHEDULER, config)

    async def _do_collect(self) -> CollectorResult:
        data = await self._fetch_json("/api/status")
        metrics: list[MetricValue] = []
        if data:
            metrics.extend([
                MetricValue(name="total_tasks", value=data.get("total_tasks", 0)),
                MetricValue(name="running_tasks", value=data.get("running_tasks", 0)),
                MetricValue(name="failed_tasks", value=data.get("failed_tasks", 0)),
                MetricValue(name="history_count", value=data.get("history_count", 0)),
            ])
        return CollectorResult(service=self.service_type.value, metrics=metrics)


COLLECTOR_MAP: dict[ServiceType, type[BaseCollector]] = {
    ServiceType.GATEWAY: GatewayCollector,
    ServiceType.ANALYTICS: AnalyticsCollector,
    ServiceType.SCADA: ScadaCollector,
    ServiceType.REPORTS: ReportsCollector,
    ServiceType.FLEET: FleetCollector,
    ServiceType.ALERT: AlertCollector,
    ServiceType.GRID: GridCollector,
    ServiceType.TWIN: TwinCollector,
    ServiceType.AUTH: AuthCollector,
    ServiceType.BACKUP: BackupCollector,
    ServiceType.SCHEDULER: SchedulerCollector,
}


def create_collector(service_type: ServiceType, config: CollectorConfig) -> BaseCollector:
    cls = COLLECTOR_MAP.get(service_type)
    if cls is None:
        raise ValueError(f"Unknown service type: {service_type}")
    return cls(config)
