"""
Feature engineering for predictive maintenance.

Extracts features from inverter telemetry data for failure prediction.
"""

from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class MaintenanceFeatureExtractor:
    """
    Extract features from inverter telemetry for maintenance prediction.

    Features include:
    - Statistical features (mean, std, min, max, skewness, kurtosis)
    - Trend features (slope, acceleration)
    - Degradation features (capacity ratio, efficiency trend)
    - Stability features (variance, coefficient of variation)
    - Operational features (hours, cycles, temperature patterns)
    """

    def __init__(self, window_size: int = 100):
        """
        Args:
            window_size: Number of recent samples to use for feature extraction
        """
        self.window_size = window_size
        self._history: dict[str, list[dict]] = {}

    def add_sample(self, inverter_id: str, data: dict):
        """
        Add a telemetry sample to the history.

        Args:
            inverter_id: Inverter identifier
            data: Telemetry data dictionary
        """
        if inverter_id not in self._history:
            self._history[inverter_id] = []

        self._history[inverter_id].append({
            "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "ac_power": data.get("ac_power"),
            "ac_voltage": data.get("ac_voltage"),
            "ac_current": data.get("ac_current"),
            "ac_frequency": data.get("ac_frequency"),
            "temperature": data.get("temperature"),
            "efficiency": data.get("efficiency"),
            "total_energy": data.get("total_energy"),
            "daily_energy": data.get("daily_energy"),
            "status": data.get("status"),
            "fault_code": data.get("fault_code"),
        })

        # Keep only recent samples
        if len(self._history[inverter_id]) > self.window_size * 3:
            self._history[inverter_id] = self._history[inverter_id][-self.window_size * 3:]

    def extract_features(self, inverter_id: str) -> dict[str, float] | None:
        """
        Extract features from the history of an inverter.

        Args:
            inverter_id: Inverter identifier

        Returns:
            Dictionary of feature_name -> value, or None if insufficient data
        """
        if inverter_id not in self._history:
            return None

        history = self._history[inverter_id]

        if len(history) < 10:
            return None

        # Use recent window
        recent = history[-self.window_size:]

        features = {}

        # Extract features for each numeric metric
        for metric in ["ac_power", "temperature", "efficiency", "ac_frequency"]:
            values = [s[metric] for s in recent if s[metric] is not None]
            if len(values) >= 5:
                features.update(self._extract_statistical_features(metric, values))
                features.update(self._extract_trend_features(metric, values))
                features.update(self._extract_stability_features(metric, values))

        # Extract cross-metric features
        features.update(self._extract_cross_metric_features(recent))

        # Extract operational features
        features.update(self._extract_operational_features(recent))

        return features

    def _extract_statistical_features(self, prefix: str, values: list[float]) -> dict[str, float]:
        """Extract statistical features from a list of values."""
        arr = np.array(values)

        features = {
            f"{prefix}_mean": float(np.mean(arr)),
            f"{prefix}_std": float(np.std(arr)),
            f"{prefix}_min": float(np.min(arr)),
            f"{prefix}_max": float(np.max(arr)),
            f"{prefix}_range": float(np.max(arr) - np.min(arr)),
            f"{prefix}_median": float(np.median(arr)),
            f"{prefix}_q25": float(np.percentile(arr, 25)),
            f"{prefix}_q75": float(np.percentile(arr, 75)),
            f"{prefix}_iqr": float(np.percentile(arr, 75) - np.percentile(arr, 25)),
        }

        # Skewness and kurtosis (need at least 8 samples)
        if len(arr) >= 8:
            mean = np.mean(arr)
            std = np.std(arr)
            if std > 0:
                normalized = (arr - mean) / std
                features[f"{prefix}_skewness"] = float(np.mean(normalized ** 3))
                features[f"{prefix}_kurtosis"] = float(np.mean(normalized ** 4) - 3)
            else:
                features[f"{prefix}_skewness"] = 0.0
                features[f"{prefix}_kurtosis"] = 0.0

        return features

    def _extract_trend_features(self, prefix: str, values: list[float]) -> dict[str, float]:
        """Extract trend features (slope, acceleration)."""
        arr = np.array(values)
        n = len(arr)

        if n < 3:
            return {}

        # Linear regression for slope
        x = np.arange(n)
        slope = np.polyfit(x, arr, 1)[0]

        # Acceleration (second derivative)
        if n >= 5:
            diffs = np.diff(arr)
            acceleration = np.polyfit(np.arange(len(diffs)), diffs, 1)[0]
        else:
            acceleration = 0.0

        # Recent trend (last 20% vs first 20%)
        split = max(1, n // 5)
        recent_mean = np.mean(arr[-split:])
        old_mean = np.mean(arr[:split])
        trend_ratio = (recent_mean - old_mean) / old_mean if old_mean != 0 else 0

        return {
            f"{prefix}_slope": float(slope),
            f"{prefix}_acceleration": float(acceleration),
            f"{prefix}_trend_ratio": float(trend_ratio),
        }

    def _extract_stability_features(self, prefix: str, values: list[float]) -> dict[str, float]:
        """Extract stability features."""
        arr = np.array(values)
        mean = np.mean(arr)
        std = np.std(arr)

        # Coefficient of variation
        cv = std / mean if mean != 0 else 0

        # Percentage of values within 1 std of mean
        within_1std = np.mean(np.abs(arr - mean) <= std)

        # Number of sign changes in first derivative
        diffs = np.diff(arr)
        sign_changes = np.sum(np.abs(np.diff(np.sign(diffs))) > 0)

        return {
            f"{prefix}_cv": float(cv),
            f"{prefix}_within_1std": float(within_1std),
            f"{prefix}_sign_changes": float(sign_changes / len(diffs) if len(diffs) > 0 else 0),
        }

    def _extract_cross_metric_features(self, history: list[dict]) -> dict[str, float]:
        """Extract features that combine multiple metrics."""
        features = {}

        # Power-temperature correlation
        power_vals = [s["ac_power"] for s in history if s["ac_power"] is not None]
        temp_vals = [s["temperature"] for s in history if s["temperature"] is not None]

        if len(power_vals) >= 10 and len(temp_vals) >= 10:
            min_len = min(len(power_vals), len(temp_vals))
            corr = np.corrcoef(power_vals[-min_len:], temp_vals[-min_len:])[0, 1]
            features["power_temperature_corr"] = float(corr) if not np.isnan(corr) else 0.0

        # Power-efficiency correlation
        eff_vals = [s["efficiency"] for s in history if s["efficiency"] is not None]
        if len(power_vals) >= 10 and len(eff_vals) >= 10:
            min_len = min(len(power_vals), len(eff_vals))
            corr = np.corrcoef(power_vals[-min_len:], eff_vals[-min_len:])[0, 1]
            features["power_efficiency_corr"] = float(corr) if not np.isnan(corr) else 0.0

        return features

    def _extract_operational_features(self, history: list[dict]) -> dict[str, float]:
        """Extract operational features."""
        features = {}

        # Total samples (proxy for operating hours)
        features["total_samples"] = float(len(history))

        # Status distribution
        statuses = [s["status"] for s in history if s["status"] is not None]
        if statuses:
            total = len(statuses)
            features["status_running_pct"] = float(statuses.count("running") / total)
            features["status_fault_pct"] = float(statuses.count("fault") / total)
            features["status_standby_pct"] = float(statuses.count("standby") / total)

        # Fault code changes (indicator of instability)
        fault_codes = [s["fault_code"] for s in history if s["fault_code"] is not None]
        if len(fault_codes) >= 2:
            changes = sum(1 for i in range(1, len(fault_codes)) if fault_codes[i] != fault_codes[i-1])
            features["fault_code_changes"] = float(changes)

        return features

    def get_history(self, inverter_id: str) -> list[dict]:
        """Get the history for an inverter."""
        return self._history.get(inverter_id, [])

    def clear_history(self, inverter_id: str | None = None):
        """Clear history for one or all inverters."""
        if inverter_id:
            self._history.pop(inverter_id, None)
        else:
            self._history.clear()

    def get_stats(self) -> dict:
        """Get extractor statistics."""
        return {
            "inverters_tracked": len(self._history),
            "total_samples": sum(len(v) for v in self._history.values()),
        }
