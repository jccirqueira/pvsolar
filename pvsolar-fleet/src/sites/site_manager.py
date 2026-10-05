"""
Site Manager Module.

Manages solar plant sites with CRUD operations and status tracking.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from src.core.config import SiteConfig, SiteStatus

logger = structlog.get_logger(__name__)


class SiteInfo:
    """Represents a managed solar plant site."""

    def __init__(self, config: SiteConfig):
        self.id = config.id or str(uuid.uuid4())[:8]
        self.name = config.name
        self.gateway_url = config.gateway_url
        self.analytics_url = config.analytics_url
        self.capacity_kw = config.capacity_kw
        self.num_inverters = config.num_inverters
        self.timezone = config.timezone
        self.latitude = config.latitude
        self.longitude = config.longitude
        self.region = config.region
        self.api_key = config.api_key
        self.status: SiteStatus = SiteStatus.OFFLINE
        self.last_update: datetime | None = None
        self.registered_at: datetime = datetime.now(UTC)
        self.tags: list[str] = []
        self.metadata: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "gateway_url": self.gateway_url,
            "analytics_url": self.analytics_url,
            "capacity_kw": self.capacity_kw,
            "num_inverters": self.num_inverters,
            "timezone": self.timezone,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "region": self.region,
            "status": self.status.value,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "registered_at": self.registered_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def update_status(self, status: SiteStatus) -> None:
        self.status = status
        self.last_update = datetime.now(UTC)

    def update_info(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and key not in ("id", "registered_at"):
                setattr(self, key, value)
        self.last_update = datetime.now(UTC)


class SiteMetrics:
    """Represents metrics for a site at a point in time."""

    def __init__(self, site_id: str):
        self.site_id = site_id
        self.timestamp: datetime = datetime.now(UTC)
        self.power_kw: float = 0.0
        self.energy_kwh: float = 0.0
        self.pr: float = 0.0
        self.efficiency: float = 0.0
        self.availability: float = 0.0
        self.cef: float = 0.0
        self.score: float = 0.0
        self.active_inverters: int = 0
        self.alarm_count: int = 0
        self.irradiance: float = 0.0
        self.temperature: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "timestamp": self.timestamp.isoformat(),
            "power_kw": self.power_kw,
            "energy_kwh": self.energy_kwh,
            "pr": self.pr,
            "efficiency": self.efficiency,
            "availability": self.availability,
            "cef": self.cef,
            "score": self.score,
            "active_inverters": self.active_inverters,
            "alarm_count": self.alarm_count,
            "irradiance": self.irradiance,
            "temperature": self.temperature,
        }


class SiteManager:
    """
    Manages solar plant sites.

    Features:
    - CRUD operations for sites
    - Status tracking
    - Metrics storage
    - Region-based grouping
    """

    def __init__(self):
        self._sites: dict[str, SiteInfo] = {}
        self._metrics: dict[str, list[SiteMetrics]] = {}
        self._max_metrics_per_site: int = 1000

    def add_site(self, config: SiteConfig) -> SiteInfo:
        site = SiteInfo(config)
        self._sites[site.id] = site
        self._metrics[site.id] = []
        logger.info("site.added", site_id=site.id, name=site.name)
        return site

    def remove_site(self, site_id: str) -> bool:
        if site_id in self._sites:
            del self._sites[site_id]
            self._metrics.pop(site_id, None)
            logger.info("site.removed", site_id=site_id)
            return True
        return False

    def get_site(self, site_id: str) -> SiteInfo | None:
        return self._sites.get(site_id)

    def get_all_sites(self) -> list[SiteInfo]:
        return list(self._sites.values())

    def get_sites_by_region(self, region: str) -> list[SiteInfo]:
        return [s for s in self._sites.values() if s.region == region]

    def get_sites_by_status(self, status: SiteStatus) -> list[SiteInfo]:
        return [s for s in self._sites.values() if s.status == status]

    def get_regions(self) -> list[str]:
        return list(set(s.region for s in self._sites.values()))

    def update_site_status(self, site_id: str, status: SiteStatus) -> bool:
        site = self._sites.get(site_id)
        if site:
            site.update_status(status)
            return True
        return False

    def update_site(self, site_id: str, **kwargs: Any) -> bool:
        site = self._sites.get(site_id)
        if site:
            site.update_info(**kwargs)
            return True
        return False

    def add_metrics(self, site_id: str, metrics: SiteMetrics) -> bool:
        if site_id not in self._metrics:
            return False
        self._metrics[site_id].append(metrics)
        if len(self._metrics[site_id]) > self._max_metrics_per_site:
            self._metrics[site_id] = self._metrics[site_id][-self._max_metrics_per_site:]
        return True

    def get_latest_metrics(self, site_id: str) -> SiteMetrics | None:
        metrics = self._metrics.get(site_id, [])
        return metrics[-1] if metrics else None

    def get_metrics_history(self, site_id: str, limit: int = 100) -> list[SiteMetrics]:
        return self._metrics.get(site_id, [])[-limit:]

    def get_site_count(self) -> int:
        return len(self._sites)

    def get_total_capacity(self) -> float:
        return sum(s.capacity_kw for s in self._sites.values())

    def get_fleet_summary(self) -> dict[str, Any]:
        sites = self.get_all_sites()
        regions = self.get_regions()
        return {
            "total_sites": len(sites),
            "total_capacity_kw": self.get_total_capacity(),
            "online_sites": len(self.get_sites_by_status(SiteStatus.ONLINE)),
            "offline_sites": len(self.get_sites_by_status(SiteStatus.OFFLINE)),
            "maintenance_sites": len(self.get_sites_by_status(SiteStatus.MAINTENANCE)),
            "degraded_sites": len(self.get_sites_by_status(SiteStatus.DEGRADED)),
            "regions": regions,
            "total_inverters": sum(s.num_inverters for s in sites),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "sites": [s.to_dict() for s in self._sites.values()],
            "summary": self.get_fleet_summary(),
        }
