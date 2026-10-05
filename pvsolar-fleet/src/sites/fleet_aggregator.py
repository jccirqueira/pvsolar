"""
Fleet Aggregator Module.

Aggregates data from all sites into fleet-wide metrics.
"""

from datetime import UTC, datetime
from typing import Any

import aiohttp
import structlog
from src.core.config import FleetConfig
from src.sites.site_manager import SiteManager, SiteMetrics

logger = structlog.get_logger(__name__)


class FleetMetrics:
    """Represents aggregated fleet metrics."""

    def __init__(self):
        self.timestamp: datetime = datetime.now(UTC)
        self.total_sites: int = 0
        self.online_sites: int = 0
        self.total_capacity_kw: float = 0.0
        self.total_power_kw: float = 0.0
        self.total_energy_kwh: float = 0.0
        self.avg_pr: float = 0.0
        self.avg_efficiency: float = 0.0
        self.avg_availability: float = 0.0
        self.total_alarms: int = 0
        self.site_metrics: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_sites": self.total_sites,
            "online_sites": self.online_sites,
            "total_capacity_kw": self.total_capacity_kw,
            "total_power_kw": self.total_power_kw,
            "total_energy_kwh": self.total_energy_kwh,
            "avg_pr": self.avg_pr,
            "avg_efficiency": self.avg_efficiency,
            "avg_availability": self.avg_availability,
            "total_alarms": self.total_alarms,
            "site_metrics": self.site_metrics,
        }


class FleetAggregator:
    """
    Aggregates data from all sites.

    Features:
    - Real-time fleet metrics
    - Energy production aggregation
    - Performance averaging
    - Region-based aggregation
    """

    def __init__(self, config: FleetConfig, site_manager: SiteManager):
        self.config = config
        self.site_manager = site_manager
        self._session: aiohttp.ClientSession | None = None
        self._fleet_metrics: list[FleetMetrics] = []

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()
        logger.info("aggregator.started")

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
        logger.info("aggregator.stopped")

    async def _fetch_site_metrics(self, site_id: str) -> SiteMetrics | None:
        site = self.site_manager.get_site(site_id)
        if not site:
            return None

        try:
            headers = {"Content-Type": "application/json"}
            if site.api_key:
                headers["Authorization"] = f"Bearer {site.api_key}"

            async with self._session.get(
                f"{site.gateway_url}/api/v1/status",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    metrics = SiteMetrics(site_id)
                    metrics.power_kw = data.get("power_kw", 0.0)
                    metrics.energy_kwh = data.get("energy_kwh", 0.0)
                    metrics.active_inverters = data.get("active_inverters", 0)
                    metrics.alarm_count = data.get("alarm_count", 0)
                    metrics.irradiance = data.get("irradiance", 0.0)
                    metrics.temperature = data.get("temperature", 0.0)
                    return metrics
        except Exception as e:
            logger.error("aggregator.fetch_error", site_id=site_id, error=str(e))

        return None

    async def _fetch_site_performance(self, site_id: str, metrics: SiteMetrics) -> None:
        site = self.site_manager.get_site(site_id)
        if not site:
            return

        try:
            headers = {"Content-Type": "application/json"}
            if site.api_key:
                headers["Authorization"] = f"Bearer {site.api_key}"

            async with self._session.get(
                f"{site.analytics_url}/api/v1/performance/current",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    metrics.pr = data.get("pr", 0.0)
                    metrics.efficiency = data.get("efficiency", 0.0)
                    metrics.availability = data.get("availability", 0.0)
                    metrics.cef = data.get("cef", 0.0)
                    metrics.score = data.get("overall_score", 0.0)
        except Exception as e:
            logger.error("aggregator.performance_error", site_id=site_id, error=str(e))

    async def collect_all_sites(self) -> list[SiteMetrics]:
        all_metrics = []
        for site in self.site_manager.get_all_sites():
            metrics = await self._fetch_site_metrics(site.id)
            if metrics:
                await self._fetch_site_performance(site.id, metrics)
                all_metrics.append(metrics)
                self.site_manager.add_metrics(site.id, metrics)
                self.site_manager.update_site_status(site.id, "online" if metrics.power_kw > 0 else "offline")
            else:
                self.site_manager.update_site_status(site.id, "offline")
        return all_metrics

    async def aggregate_fleet(self) -> FleetMetrics:
        all_metrics = await self.collect_all_sites()

        fleet = FleetMetrics()
        fleet.total_sites = len(all_metrics)
        fleet.online_sites = sum(1 for m in all_metrics if m.power_kw > 0)
        fleet.total_capacity_kw = self.site_manager.get_total_capacity()
        fleet.total_power_kw = sum(m.power_kw for m in all_metrics)
        fleet.total_energy_kwh = sum(m.energy_kwh for m in all_metrics)
        fleet.total_alarms = sum(m.alarm_count for m in all_metrics)

        if all_metrics:
            fleet.avg_pr = sum(m.pr for m in all_metrics) / len(all_metrics)
            fleet.avg_efficiency = sum(m.efficiency for m in all_metrics) / len(all_metrics)
            fleet.avg_availability = sum(m.availability for m in all_metrics) / len(all_metrics)

        fleet.site_metrics = [m.to_dict() for m in all_metrics]

        self._fleet_metrics.append(fleet)
        if len(self._fleet_metrics) > 1000:
            self._fleet_metrics = self._fleet_metrics[-1000:]

        logger.info(
            "aggregator.fleet_aggregated",
            total_sites=fleet.total_sites,
            online=fleet.online_sites,
            total_power=fleet.total_power_kw,
        )

        return fleet

    def get_latest_fleet_metrics(self) -> FleetMetrics | None:
        return self._fleet_metrics[-1] if self._fleet_metrics else None

    def get_fleet_history(self, limit: int = 100) -> list[FleetMetrics]:
        return self._fleet_metrics[-limit:]

    def get_region_aggregation(self, region: str) -> dict[str, Any]:
        sites = self.site_manager.get_sites_by_region(region)
        metrics = []
        for site in sites:
            site_metrics = self.site_manager.get_latest_metrics(site.id)
            if site_metrics:
                metrics.append(site_metrics)

        if not metrics:
            return {"region": region, "sites": 0, "total_power_kw": 0.0, "avg_pr": 0.0}

        return {
            "region": region,
            "sites": len(sites),
            "total_power_kw": sum(m.power_kw for m in metrics),
            "total_energy_kwh": sum(m.energy_kwh for m in metrics),
            "avg_pr": sum(m.pr for m in metrics) / len(metrics),
            "avg_efficiency": sum(m.efficiency for m in metrics) / len(metrics),
        }

    def get_all_regions_aggregation(self) -> list[dict[str, Any]]:
        regions = self.site_manager.get_regions()
        return [self.get_region_aggregation(r) for r in regions]
