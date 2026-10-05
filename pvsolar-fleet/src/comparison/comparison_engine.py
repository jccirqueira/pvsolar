"""
Comparison Engine Module.

Compares and ranks sites across the fleet.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from src.core.config import ComparisonMetric
from src.sites.site_manager import SiteManager, SiteMetrics

logger = structlog.get_logger(__name__)


class SiteRanking:
    """Represents a site's ranking position."""

    def __init__(self, site_id: str, site_name: str, metric: ComparisonMetric, value: float, rank: int):
        self.site_id = site_id
        self.site_name = site_name
        self.metric = metric
        self.value = value
        self.rank = rank
        self.timestamp: datetime = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "site_name": self.site_name,
            "metric": self.metric.value,
            "value": self.value,
            "rank": self.rank,
            "timestamp": self.timestamp.isoformat(),
        }


class ComparisonResult:
    """Result of a comparison operation."""

    def __init__(self, metric: ComparisonMetric):
        self.metric = metric
        self.timestamp: datetime = datetime.now(UTC)
        self.rankings: list[SiteRanking] = []
        self.avg_value: float = 0.0
        self.best_site: str | None = None
        self.worst_site: str | None = None
        self.fleet_total: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric.value,
            "timestamp": self.timestamp.isoformat(),
            "rankings": [r.to_dict() for r in self.rankings],
            "avg_value": self.avg_value,
            "best_site": self.best_site,
            "worst_site": self.worst_site,
            "fleet_total": self.fleet_total,
        }


class ComparisonEngine:
    """
    Compares and ranks sites.

    Features:
    - Multi-metric comparison
    - Fleet ranking
    - Peer group comparison
    - Trend analysis
    """

    def __init__(self, site_manager: SiteManager):
        self.site_manager = site_manager
        self._history: list[ComparisonResult] = []

    def _get_metric_value(self, metrics: SiteMetrics, metric: ComparisonMetric) -> float:
        metric_map = {
            ComparisonMetric.ENERGY: metrics.energy_kwh,
            ComparisonMetric.PR: metrics.pr,
            ComparisonMetric.EFFICIENCY: metrics.efficiency,
            ComparisonMetric.AVAILABILITY: metrics.availability,
            ComparisonMetric.CEF: metrics.cef,
            ComparisonMetric.SCORE: metrics.score,
        }
        return metric_map.get(metric, 0.0)

    def compare_sites(self, metric: ComparisonMetric) -> ComparisonResult:
        result = ComparisonResult(metric)
        rankings = []

        for site in self.site_manager.get_all_sites():
            metrics = self.site_manager.get_latest_metrics(site.id)
            if metrics:
                value = self._get_metric_value(metrics, metric)
                rankings.append(SiteRanking(site.id, site.name, metric, value, 0))

        rankings.sort(key=lambda r: r.value, reverse=True)
        for i, ranking in enumerate(rankings):
            ranking.rank = i + 1

        result.rankings = rankings
        if rankings:
            result.avg_value = sum(r.value for r in rankings) / len(rankings)
            result.best_site = rankings[0].site_name
            result.worst_site = rankings[-1].site_name
        result.fleet_total = sum(r.value for r in rankings)

        self._history.append(result)
        logger.info(
            "comparison.completed",
            metric=metric.value,
            sites=len(rankings),
            best=result.best_site,
        )
        return result

    def compare_all_metrics(self) -> dict[str, ComparisonResult]:
        results = {}
        for metric in ComparisonMetric:
            results[metric.value] = self.compare_sites(metric)
        return results

    def get_peer_group(self, site_id: str, metric: ComparisonMetric, group_size: int = 5) -> list[SiteRanking]:
        result = self.compare_sites(metric)
        site_rank = None
        for ranking in result.rankings:
            if ranking.site_id == site_id:
                site_rank = ranking.rank
                break

        if site_rank is None:
            return []

        start = max(0, site_rank - group_size // 2)
        end = min(len(result.rankings), start + group_size)
        return result.rankings[start:end]

    def get_vs_average(self, site_id: str, metric: ComparisonMetric) -> dict[str, Any]:
        result = self.compare_sites(metric)
        site_value = None
        for ranking in result.rankings:
            if ranking.site_id == site_id:
                site_value = ranking.value
                break

        if site_value is None:
            return {"site_id": site_id, "metric": metric.value, "vs_avg": 0.0, "diff": 0.0}

        diff = site_value - result.avg_value
        pct = (diff / result.avg_value * 100) if result.avg_value > 0 else 0.0

        return {
            "site_id": site_id,
            "metric": metric.value,
            "site_value": site_value,
            "fleet_avg": result.avg_value,
            "diff": diff,
            "vs_avg_percent": round(pct, 2),
        }

    def get_vs_best(self, site_id: str, metric: ComparisonMetric) -> dict[str, Any]:
        result = self.compare_sites(metric)
        site_value = None
        best_value = None
        for ranking in result.rankings:
            if ranking.site_id == site_id:
                site_value = ranking.value
            if ranking.rank == 1:
                best_value = ranking.value

        if site_value is None or best_value is None:
            return {"site_id": site_id, "metric": metric.value, "diff": 0.0}

        diff = best_value - site_value
        return {
            "site_id": site_id,
            "metric": metric.value,
            "site_value": site_value,
            "best_value": best_value,
            "diff": diff,
            "gap_percent": round((diff / best_value * 100) if best_value > 0 else 0.0, 2),
        }

    def get_worst_performers(self, metric: ComparisonMetric, count: int = 3) -> list[SiteRanking]:
        result = self.compare_sites(metric)
        return result.rankings[-count:] if len(result.rankings) >= count else result.rankings

    def get_best_performers(self, metric: ComparisonMetric, count: int = 3) -> list[SiteRanking]:
        result = self.compare_sites(metric)
        return result.rankings[:count]

    def get_comparison_history(self, limit: int = 10) -> list[ComparisonResult]:
        return self._history[-limit:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_count": len(self._history),
            "latest": self._history[-1].to_dict() if self._history else None,
        }
