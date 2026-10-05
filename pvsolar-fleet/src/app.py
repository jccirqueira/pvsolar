"""
pvSolar Fleet Application.

Main application that initializes and runs the fleet management system.
"""

import contextlib
from typing import Any

import structlog
from src.alerts.alert_aggregator import AlertAggregator
from src.comparison.comparison_engine import ComparisonEngine
from src.core.config import AlertSeverity, ComparisonMetric, FleetConfig, SiteConfig, load_config
from src.sites.fleet_aggregator import FleetAggregator
from src.sites.site_manager import SiteManager

logger = structlog.get_logger(__name__)


class PVSolarFleet:
    """
    pvSolar Fleet Application.

    Main application class that initializes and manages:
    - Site management (CRUD)
    - Fleet aggregation
    - Alert aggregation
    - Comparison engine
    """

    def __init__(self, config: FleetConfig | None = None, config_path: str | None = None):
        if config:
            self.config = config
        else:
            self.config = load_config(config_path)

        self.site_manager = SiteManager()
        self.fleet_aggregator = FleetAggregator(self.config, self.site_manager)
        self.alert_aggregator = AlertAggregator(max_alerts=self.config.alerts.max_alerts_per_site)
        self.comparison_engine = ComparisonEngine(self.site_manager)
        self._running = False

    async def start(self) -> None:
        logger.info("fleet.starting")
        await self.fleet_aggregator.start()

        for site_config in self.config.sites:
            self.site_manager.add_site(site_config)

        self._running = True
        logger.info("fleet.started", sites=len(self.config.sites))

    async def stop(self) -> None:
        logger.info("fleet.stopping")
        await self.fleet_aggregator.stop()
        self._running = False
        logger.info("fleet.stopped")

    def add_site(self, config: SiteConfig) -> dict[str, Any]:
        site = self.site_manager.add_site(config)
        logger.info("fleet.site_added", site_id=site.id, name=site.name)
        return site.to_dict()

    def remove_site(self, site_id: str) -> bool:
        result = self.site_manager.remove_site(site_id)
        if result:
            logger.info("fleet.site_removed", site_id=site_id)
        return result

    def get_site(self, site_id: str) -> dict[str, Any] | None:
        site = self.site_manager.get_site(site_id)
        return site.to_dict() if site else None

    def get_all_sites(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.site_manager.get_all_sites()]

    def get_fleet_summary(self) -> dict[str, Any]:
        return self.site_manager.get_fleet_summary()

    async def refresh_fleet(self) -> dict[str, Any]:
        fleet_metrics = await self.fleet_aggregator.aggregate_fleet()
        return fleet_metrics.to_dict()

    def get_fleet_metrics(self) -> dict[str, Any] | None:
        metrics = self.fleet_aggregator.get_latest_fleet_metrics()
        return metrics.to_dict() if metrics else None

    def compare_sites(self, metric: str = "pr") -> dict[str, Any]:
        try:
            m = ComparisonMetric(metric)
        except ValueError:
            m = ComparisonMetric.PR
        result = self.comparison_engine.compare_sites(m)
        return result.to_dict()

    def get_site_ranking(self, site_id: str, metric: str = "pr") -> dict[str, Any]:
        try:
            m = ComparisonMetric(metric)
        except ValueError:
            m = ComparisonMetric.PR
        return self.comparison_engine.get_vs_average(site_id, m)

    def get_best_performers(self, metric: str = "pr", count: int = 3) -> list[dict[str, Any]]:
        try:
            m = ComparisonMetric(metric)
        except ValueError:
            m = ComparisonMetric.PR
        return [r.to_dict() for r in self.comparison_engine.get_best_performers(m, count)]

    def get_worst_performers(self, metric: str = "pr", count: int = 3) -> list[dict[str, Any]]:
        try:
            m = ComparisonMetric(metric)
        except ValueError:
            m = ComparisonMetric.PR
        return [r.to_dict() for r in self.comparison_engine.get_worst_performers(m, count)]

    def create_alert(
        self,
        site_id: str,
        severity: str,
        message: str,
        source: str = "",
    ) -> dict[str, Any]:
        site = self.site_manager.get_site(site_id)
        site_name = site.name if site else "Unknown"
        try:
            s = AlertSeverity(severity)
        except ValueError:
            s = AlertSeverity.INFO
        alert = self.alert_aggregator.create_alert(site_id, site_name, s, message, source)
        return alert.to_dict()

    def acknowledge_alert(self, alert_id: str, user: str = "operator") -> bool:
        return self.alert_aggregator.acknowledge_alert(alert_id, user)

    def resolve_alert(self, alert_id: str) -> bool:
        return self.alert_aggregator.resolve_alert(alert_id)

    def get_alerts(self, site_id: str | None = None, severity: str | None = None) -> list[dict[str, Any]]:
        s = None
        if severity:
            with contextlib.suppress(ValueError):
                s = AlertSeverity(severity)
        alerts = self.alert_aggregator.get_alerts(site_id=site_id, severity=s)
        return [a.to_dict() for a in alerts]

    def get_alert_statistics(self) -> dict[str, Any]:
        return self.alert_aggregator.get_statistics()

    def get_regions(self) -> list[str]:
        return self.site_manager.get_regions()

    def get_region_summary(self, region: str) -> dict[str, Any]:
        return self.fleet_aggregator.get_region_aggregation(region)

    def is_running(self) -> bool:
        return self._running
