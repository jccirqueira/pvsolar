"""
Performance benchmarking for solar inverters.

Compares inverter performance against fleet averages, peer groups,
and historical baselines.
"""

from datetime import UTC, datetime

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class BenchmarkResult:
    """Result of a performance benchmark comparison."""

    def __init__(
        self,
        inverter_id: str,
        overall_rank: float,
        fleet_percentile: float,
        vs_fleet_avg: float,
        vs_peer_avg: float,
        vs_historical: float,
        peer_group: str,
        metrics: dict | None = None,
    ):
        self.inverter_id = inverter_id
        self.overall_rank = overall_rank
        self.fleet_percentile = fleet_percentile
        self.vs_fleet_avg = vs_fleet_avg
        self.vs_peer_avg = vs_peer_avg
        self.vs_historical = vs_historical
        self.peer_group = peer_group
        self.metrics = metrics or {}

    def to_dict(self) -> dict:
        return {
            "inverter_id": self.inverter_id,
            "overall_rank": self.overall_rank,
            "fleet_percentile": self.fleet_percentile,
            "vs_fleet_avg": self.vs_fleet_avg,
            "vs_peer_avg": self.vs_peer_avg,
            "vs_historical": self.vs_historical,
            "peer_group": self.peer_group,
            "metrics": self.metrics,
        }


class PerformanceBenchmark:
    """
    Benchmark inverter performance against fleet and peers.

    Supports:
    - Fleet ranking (percentile)
    - Peer group comparison (by model, capacity, region)
    - Historical trend comparison
    - Anomaly detection in performance patterns
    """

    def __init__(self, peer_group_key: str = "model"):
        """
        Args:
            peer_group_key: Key to group inverters (model, capacity, region, etc.)
        """
        self.peer_group_key = peer_group_key
        self._fleet_scores: dict[str, dict] = {}
        self._peer_groups: dict[str, list[str]] = {}
        self._historical: dict[str, list[dict]] = {}

    def add_inverter_score(self, inverter_id: str, score: dict, peer_group: str = "default"):
        """
        Add an inverter's performance score to the fleet.

        Args:
            inverter_id: Inverter identifier
            score: Performance score dictionary
            peer_group: Peer group identifier
        """
        self._fleet_scores[inverter_id] = {
            "score": score,
            "peer_group": peer_group,
            "timestamp": datetime.now(UTC),
        }

        # Update peer group mapping
        if peer_group not in self._peer_groups:
            self._peer_groups[peer_group] = []
        if inverter_id not in self._peer_groups[peer_group]:
            self._peer_groups[peer_group].append(inverter_id)

        # Update historical
        if inverter_id not in self._historical:
            self._historical[inverter_id] = []

        self._historical[inverter_id].append({
            "score": score,
            "timestamp": datetime.now(UTC),
        })

        # Keep bounded
        max_history = 365  # 1 year of daily scores
        if len(self._historical[inverter_id]) > max_history:
            self._historical[inverter_id] = self._historical[inverter_id][-max_history:]

    def benchmark(self, inverter_id: str) -> BenchmarkResult | None:
        """
        Generate a benchmark result for an inverter.

        Args:
            inverter_id: Inverter identifier

        Returns:
            BenchmarkResult or None if no data
        """
        if inverter_id not in self._fleet_scores:
            return None

        inverter_data = self._fleet_scores[inverter_id]
        inverter_score = inverter_data["score"]
        peer_group = inverter_data["peer_group"]

        # Fleet ranking
        fleet_percentile = self._calculate_fleet_percentile(inverter_id, inverter_score)

        # Fleet average comparison
        vs_fleet_avg = self._compare_to_fleet_average(inverter_id, inverter_score)

        # Peer group comparison
        vs_peer_avg = self._compare_to_peer_average(inverter_id, peer_group, inverter_score)

        # Historical comparison
        vs_historical = self._compare_to_historical(inverter_id, inverter_score)

        # Overall rank (1-100 percentile)
        overall_rank = fleet_percentile

        # Build metrics breakdown
        metrics = self._build_metrics(inverter_score)

        return BenchmarkResult(
            inverter_id=inverter_id,
            overall_rank=overall_rank,
            fleet_percentile=fleet_percentile,
            vs_fleet_avg=vs_fleet_avg,
            vs_peer_avg=vs_peer_avg,
            vs_historical=vs_historical,
            peer_group=peer_group,
            metrics=metrics,
        )

    def _calculate_fleet_percentile(self, inverter_id: str, score: dict) -> float:
        """Calculate the inverter's percentile rank in the fleet."""
        if len(self._fleet_scores) <= 1:
            return 50.0

        overall = score.get("overall_score", 0)

        # Count inverters with lower scores
        lower_count = 0
        for inv_id, data in self._fleet_scores.items():
            if inv_id != inverter_id:
                other_score = data["score"].get("overall_score", 0)
                if other_score < overall:
                    lower_count += 1

        percentile = (lower_count / (len(self._fleet_scores) - 1)) * 100

        return float(np.clip(percentile, 0, 100))

    def _compare_to_fleet_average(self, inverter_id: str, score: dict) -> float:
        """Calculate percentage difference from fleet average."""
        if len(self._fleet_scores) <= 1:
            return 0.0

        fleet_overalls = [
            data["score"].get("overall_score", 0)
            for inv_id, data in self._fleet_scores.items()
            if inv_id != inverter_id
        ]

        if not fleet_overalls:
            return 0.0

        fleet_avg = np.mean(fleet_overalls)
        inverter_overall = score.get("overall_score", 0)

        if fleet_avg == 0:
            return 0.0

        return ((inverter_overall - fleet_avg) / fleet_avg) * 100

    def _compare_to_peer_average(
        self,
        inverter_id: str,
        peer_group: str,
        score: dict,
    ) -> float:
        """Calculate percentage difference from peer group average."""
        peer_ids = self._peer_groups.get(peer_group, [])
        peer_ids = [pid for pid in peer_ids if pid != inverter_id]

        if not peer_ids:
            return 0.0

        peer_overalls = [
            self._fleet_scores[pid]["score"].get("overall_score", 0)
            for pid in peer_ids
            if pid in self._fleet_scores
        ]

        if not peer_overalls:
            return 0.0

        peer_avg = np.mean(peer_overalls)
        inverter_overall = score.get("overall_score", 0)

        if peer_avg == 0:
            return 0.0

        return ((inverter_overall - peer_avg) / peer_avg) * 100

    def _compare_to_historical(self, inverter_id: str, current_score: dict) -> float:
        """Compare current score to historical average."""
        history = self._historical.get(inverter_id, [])

        if len(history) <= 1:
            return 0.0

        # Use historical scores (excluding current)
        historical_scores = [
            h["score"].get("overall_score", 0)
            for h in history[:-1]
        ]

        if not historical_scores:
            return 0.0

        hist_avg = np.mean(historical_scores)
        current = current_score.get("overall_score", 0)

        if hist_avg == 0:
            return 0.0

        return ((current - hist_avg) / hist_avg) * 100

    def _build_metrics(self, score: dict) -> dict:
        """Build detailed metrics from score."""
        return {
            "overall_score": score.get("overall_score", 0),
            "performance_ratio": score.get("performance_ratio", 0),
            "calendar_energy_factor": score.get("calendar_energy_factor", 0),
            "availability": score.get("availability", 0),
            "efficiency": score.get("efficiency", 0),
            "grade": score.get("grade", "N/A"),
        }

    def get_fleet_stats(self) -> dict:
        """Get fleet-wide statistics."""
        if not self._fleet_scores:
            return {
                "total_inverters": 0,
                "peer_groups": 0,
            }

        overall_scores = [
            data["score"].get("overall_score", 0)
            for data in self._fleet_scores.values()
        ]

        return {
            "total_inverters": len(self._fleet_scores),
            "peer_groups": len(self._peer_groups),
            "fleet_mean": float(np.mean(overall_scores)),
            "fleet_std": float(np.std(overall_scores)),
            "fleet_min": float(np.min(overall_scores)),
            "fleet_max": float(np.max(overall_scores)),
        }

    def get_peer_group_stats(self, peer_group: str) -> dict:
        """Get statistics for a specific peer group."""
        peer_ids = self._peer_groups.get(peer_group, [])

        if not peer_ids:
            return {"count": 0}

        scores = [
            self._fleet_scores[pid]["score"].get("overall_score", 0)
            for pid in peer_ids
            if pid in self._fleet_scores
        ]

        if not scores:
            return {"count": 0}

        return {
            "count": len(scores),
            "mean": float(np.mean(scores)),
            "std": float(np.std(scores)),
            "min": float(np.min(scores)),
            "max": float(np.max(scores)),
        }

    def get_stats(self) -> dict:
        """Get benchmark statistics."""
        return {
            "fleet_size": len(self._fleet_scores),
            "peer_groups": len(self._peer_groups),
            "historical_inverters": len(self._historical),
        }
