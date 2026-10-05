"""
Anomaly detection for solar inverter telemetry.

Implements:
- Isolation Forest for multivariate anomaly detection
- Statistical Process Control (SPC) for univariate monitoring
- Z-score based detection
- Rolling statistics anomaly detection
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

import numpy as np
import structlog
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    """Types of anomalies detected."""
    ISOLATION_FOREST = "isolation_forest"
    ZSCORE = "zscore"
    ROLLING_MEAN = "rolling_mean"
    THRESHOLD = "threshold"
    SPC = "spc"


class AnomalyResult:
    """Result of an anomaly detection."""

    def __init__(
        self,
        metric: str,
        value: float,
        score: float,
        threshold: float,
        severity: AnomalySeverity,
        anomaly_type: AnomalyType,
        description: str,
        timestamp: datetime | None = None,
    ):
        self.metric = metric
        self.value = value
        self.score = score
        self.threshold = threshold
        self.severity = severity
        self.anomaly_type = anomaly_type
        self.description = description
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "value": self.value,
            "score": self.score,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "anomaly_type": self.anomaly_type.value,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
        }


class IsolationForestDetector:
    """
    Multivariate anomaly detection using Isolation Forest.

    Good for detecting unusual combinations of features
    (e.g., high power but low voltage).
    """

    def __init__(self, contamination: float = 0.05, n_estimators: int = 100):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self._model: IsolationForest | None = None
        self._scaler: StandardScaler | None = None
        self._feature_names: list[str] = []
        self._fitted = False

    def fit(self, data: np.ndarray, feature_names: list[str] | None = None):
        """
        Fit the Isolation Forest model on historical data.

        Args:
            data: 2D array of shape (n_samples, n_features)
            feature_names: Optional feature names for reporting
        """
        if data.ndim != 2 or data.shape[0] < 10:
            raise ValueError("Need at least 10 samples with multiple features")

        self._feature_names = feature_names or [f"feature_{i}" for i in range(data.shape[1])]

        self._scaler = StandardScaler()
        data_scaled = self._scaler.fit_transform(data)

        self._model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=42,
            n_jobs=-1,
        )
        self._model.fit(data_scaled)
        self._fitted = True

        logger.info(
            "isolation_forest.fitted",
            samples=data.shape[0],
            features=data.shape[1],
            contamination=self.contamination,
        )

    def predict(self, data: np.ndarray) -> np.ndarray:
        """
        Predict anomalies.

        Args:
            data: 2D array of shape (n_samples, n_features)

        Returns:
            Array of -1 (anomaly) or 1 (normal)
        """
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        data_scaled = self._scaler.transform(data)
        return self._model.predict(data_scaled)

    def score(self, data: np.ndarray) -> np.ndarray:
        """
        Get anomaly scores (lower = more anomalous).

        Args:
            data: 2D array of shape (n_samples, n_features)

        Returns:
            Array of anomaly scores
        """
        if not self._fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        data_scaled = self._scaler.transform(data)
        return self._model.score_samples(data_scaled)

    def detect(self, data: np.ndarray) -> list[AnomalyResult]:
        """
        Detect anomalies and return detailed results.

        Args:
            data: 2D array of shape (n_samples, n_features)

        Returns:
            List of AnomalyResult for each detected anomaly
        """
        predictions = self.predict(data)
        scores = self.score(data)
        results = []

        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred == -1:  # Anomaly
                severity = self._score_to_severity(score)
                # Find which features contributed most
                feature_importance = self._get_feature_importance(data[i])

                results.append(AnomalyResult(
                    metric="multivariate",
                    value=float(score),
                    score=float(-score),  # Convert to 0-1 scale (higher = more anomalous)
                    threshold=0.5,
                    severity=severity,
                    anomaly_type=AnomalyType.ISOLATION_FOREST,
                    description=f"Multivariate anomaly detected: {feature_importance}",
                ))

        return results

    def _score_to_severity(self, score: float) -> AnomalySeverity:
        """Convert Isolation Forest score to severity level."""
        if score < -0.5:
            return AnomalySeverity.CRITICAL
        elif score < -0.3:
            return AnomalySeverity.ERROR
        elif score < -0.1:
            return AnomalySeverity.WARNING
        return AnomalySeverity.INFO

    def _get_feature_importance(self, sample: np.ndarray) -> str:
        """Get which features contributed most to the anomaly."""
        if self._scaler is None:
            return "unknown features"

        sample_scaled = self._scaler.transform(sample.reshape(1, -1))[0]
        abs_values = np.abs(sample_scaled)
        top_indices = np.argsort(abs_values)[-3:][::-1]

        important_features = []
        for idx in top_indices:
            if idx < len(self._feature_names):
                important_features.append(self._feature_names[idx])

        return ", ".join(important_features) if important_features else "unknown"


class ZScoreDetector:
    """
    Univariate anomaly detection using Z-score.

    Detects values that deviate significantly from the mean.
    """

    def __init__(self, threshold: float = 3.0, min_samples: int = 30):
        self.threshold = threshold
        self.min_samples = min_samples
        self._history: dict[str, list[float]] = {}

    def update(self, metric: str, value: float):
        """Add a new value to the history for a metric."""
        if metric not in self._history:
            self._history[metric] = []
        self._history[metric].append(value)

        # Keep only recent values (rolling window)
        if len(self._history[metric]) > 1000:
            self._history[metric] = self._history[metric][-1000:]

    def detect(self, metric: str, value: float) -> AnomalyResult | None:
        """
        Check if a value is anomalous based on Z-score.

        Args:
            metric: Metric name
            value: Current value

        Returns:
            AnomalyResult if anomalous, None otherwise
        """
        if metric not in self._history:
            self.update(metric, value)
            return None

        history = self._history[metric]

        if len(history) < self.min_samples:
            self.update(metric, value)
            return None

        mean = np.mean(history)
        std = np.std(history)

        if std == 0:
            self.update(metric, value)
            return None

        z_score = abs(value - mean) / std

        if z_score > self.threshold:
            severity = self._zscore_to_severity(z_score)
            deviation_pct = ((value - mean) / mean) * 100 if mean != 0 else 0

            result = AnomalyResult(
                metric=metric,
                value=value,
                score=min(z_score / 10.0, 1.0),  # Normalize to 0-1
                threshold=self.threshold,
                severity=severity,
                anomaly_type=AnomalyType.ZSCORE,
                description=(
                    f"Z-score {z_score:.2f} exceeds threshold {self.threshold}. "
                    f"Value {value:.2f} deviates {deviation_pct:+.1f}% from mean {mean:.2f}"
                ),
            )

            self.update(metric, value)
            return result

        self.update(metric, value)
        return None

    def _zscore_to_severity(self, z_score: float) -> AnomalySeverity:
        """Convert Z-score to severity level."""
        if z_score > 5.0:
            return AnomalySeverity.CRITICAL
        elif z_score > 4.0:
            return AnomalySeverity.ERROR
        elif z_score > 3.0:
            return AnomalySeverity.WARNING
        return AnomalySeverity.INFO


class RollingMeanDetector:
    """
    Anomaly detection using rolling mean and standard deviation.

    Detects sudden changes in the rolling statistics.
    """

    def __init__(self, window: int = 20, threshold: float = 2.5):
        self.window = window
        self.threshold = threshold
        self._history: dict[str, list[float]] = {}

    def update(self, metric: str, value: float):
        """Add a new value to the history."""
        if metric not in self._history:
            self._history[metric] = []
        self._history[metric].append(value)

        if len(self._history[metric]) > self.window * 3:
            self._history[metric] = self._history[metric][-self.window * 3:]

    def detect(self, metric: str, value: float) -> AnomalyResult | None:
        """
        Check if a value deviates from rolling statistics.

        Args:
            metric: Metric name
            value: Current value

        Returns:
            AnomalyResult if anomalous, None otherwise
        """
        if metric not in self._history:
            self.update(metric, value)
            return None

        history = self._history[metric]

        if len(history) < self.window:
            self.update(metric, value)
            return None

        rolling_data = history[-self.window:]
        rolling_mean = np.mean(rolling_data)
        rolling_std = np.std(rolling_data)

        if rolling_std == 0:
            self.update(metric, value)
            return None

        deviation = abs(value - rolling_mean) / rolling_std

        if deviation > self.threshold:
            severity = self._deviation_to_severity(deviation)

            result = AnomalyResult(
                metric=metric,
                value=value,
                score=min(deviation / 10.0, 1.0),
                threshold=self.threshold,
                severity=severity,
                anomaly_type=AnomalyType.ROLLING_MEAN,
                description=(
                    f"Value {value:.2f} deviates {deviation:.2f} std from "
                    f"rolling mean {rolling_mean:.2f} (window={self.window})"
                ),
            )

            self.update(metric, value)
            return result

        self.update(metric, value)
        return None

    def _deviation_to_severity(self, deviation: float) -> AnomalySeverity:
        """Convert deviation to severity level."""
        if deviation > 5.0:
            return AnomalySeverity.CRITICAL
        elif deviation > 4.0:
            return AnomalySeverity.ERROR
        elif deviation > 2.5:
            return AnomalySeverity.WARNING
        return AnomalySeverity.INFO


class ThresholdDetector:
    """
    Simple threshold-based anomaly detection.

    Detects values outside expected ranges.
    """

    def __init__(self):
        self._thresholds: dict[str, dict[str, float]] = {}

    def set_threshold(
        self,
        metric: str,
        min_value: float | None = None,
        max_value: float | None = None,
    ):
        """Set thresholds for a metric."""
        self._thresholds[metric] = {
            "min": min_value,
            "max": max_value,
        }

    def detect(self, metric: str, value: float) -> AnomalyResult | None:
        """
        Check if a value exceeds thresholds.

        Args:
            metric: Metric name
            value: Current value

        Returns:
            AnomalyResult if anomalous, None otherwise
        """
        if metric not in self._thresholds:
            return None

        thresholds = self._thresholds[metric]
        min_val = thresholds.get("min")
        max_val = thresholds.get("max")

        if min_val is not None and value < min_val:
            return AnomalyResult(
                metric=metric,
                value=value,
                score=0.8,
                threshold=min_val,
                severity=AnomalySeverity.WARNING,
                anomaly_type=AnomalyType.THRESHOLD,
                description=f"Value {value:.2f} below minimum threshold {min_val:.2f}",
            )

        if max_val is not None and value > max_val:
            return AnomalyResult(
                metric=metric,
                value=value,
                score=0.8,
                threshold=max_val,
                severity=AnomalySeverity.WARNING,
                anomaly_type=AnomalyType.THRESHOLD,
                description=f"Value {value:.2f} above maximum threshold {max_val:.2f}",
            )

        return None


class SPCDetector:
    """
    Statistical Process Control (SPC) detector.

    Uses control charts (X-bar, R-chart) to detect process anomalies.
    """

    def __init__(self, window: int = 25, sigma: float = 3.0):
        self.window = window
        self.sigma = sigma
        self._history: dict[str, list[float]] = {}

    def update(self, metric: str, value: float):
        """Add a new value to the history."""
        if metric not in self._history:
            self._history[metric] = []
        self._history[metric].append(value)

        if len(self._history[metric]) > self.window * 5:
            self._history[metric] = self._history[metric][-self.window * 5:]

    def detect(self, metric: str, value: float) -> AnomalyResult | None:
        """
        Check if a value violates SPC control limits.

        Args:
            metric: Metric name
            value: Current value

        Returns:
            AnomalyResult if anomalous, None otherwise
        """
        if metric not in self._history:
            self.update(metric, value)
            return None

        history = self._history[metric]

        if len(history) < self.window:
            self.update(metric, value)
            return None

        # Calculate control limits from recent history
        recent = history[-self.window:]
        center_line = np.mean(recent)
        range_val = np.ptp(recent)  # Peak to peak (max - min)

        # Avoid division by zero
        if range_val == 0:
            self.update(metric, value)
            return None

        # Estimate sigma from range
        estimated_sigma = range_val / 6  # Approximation for normal distribution

        # Control limits
        ucl = center_line + self.sigma * estimated_sigma
        lcl = center_line - self.sigma * estimated_sigma

        # Check for violations
        if value > ucl or value < lcl:
            deviation = abs(value - center_line) / estimated_sigma if estimated_sigma > 0 else 0
            severity = self._violation_to_severity(deviation, self.sigma)

            zone = self._get_zone(value, center_line, estimated_sigma)

            result = AnomalyResult(
                metric=metric,
                value=value,
                score=min(deviation / 10.0, 1.0),
                threshold=ucl if value > ucl else lcl,
                severity=severity,
                anomaly_type=AnomalyType.SPC,
                description=(
                    f"SPC violation in Zone {zone}: value {value:.2f} outside "
                    f"control limits [{lcl:.2f}, {ucl:.2f}] (center={center_line:.2f})"
                ),
            )

            self.update(metric, value)
            return result

        self.update(metric, value)
        return None

    def _get_zone(self, value: float, center: float, sigma: float) -> str:
        """Determine which SPC zone the value falls in."""
        if sigma == 0:
            return "C"

        deviation = abs(value - center) / sigma

        if deviation > 3:
            return "A-beyond"
        elif deviation > 2:
            return "A"
        elif deviation > 1:
            return "B"
        return "C"

    def _violation_to_severity(self, deviation: float, sigma_limit: float) -> AnomalySeverity:
        """Convert violation deviation to severity."""
        ratio = deviation / sigma_limit
        if ratio > 2:
            return AnomalySeverity.CRITICAL
        elif ratio > 1.5:
            return AnomalySeverity.ERROR
        elif ratio > 1:
            return AnomalySeverity.WARNING
        return AnomalySeverity.INFO


class AnomalyDetector:
    """
    Combined anomaly detector using multiple methods.

    Runs all detectors and aggregates results.
    """

    def __init__(
        self,
        contamination: float = 0.05,
        zscore_threshold: float = 3.0,
        rolling_window: int = 20,
        spc_window: int = 25,
    ):
        self.isolation_forest = IsolationForestDetector(contamination=contamination)
        self.zscore = ZScoreDetector(threshold=zscore_threshold)
        self.rolling_mean = RollingMeanDetector(window=rolling_window)
        self.spc = SPCDetector(window=spc_window)
        self.threshold = ThresholdDetector()

        self._setup_default_thresholds()

    def _setup_default_thresholds(self):
        """Setup default thresholds for common inverter metrics."""
        self.threshold.set_threshold("ac_power", min_value=0, max_value=100000)
        self.threshold.set_threshold("ac_voltage", min_value=100, max_value=500)
        self.threshold.set_threshold("ac_frequency", min_value=45, max_value=65)
        self.threshold.set_threshold("temperature", min_value=-20, max_value=100)
        self.threshold.set_threshold("efficiency", min_value=0, max_value=100)
        self.threshold.set_threshold("dc_voltage", min_value=0, max_value=1000)

    def fit_isolation_forest(self, data: np.ndarray, feature_names: list[str] | None = None):
        """Fit the Isolation Forest model on historical data."""
        self.isolation_forest.fit(data, feature_names)

    def detect(self, metrics: dict[str, float]) -> list[AnomalyResult]:
        """
        Run all detectors on the given metrics.

        Args:
            metrics: Dictionary of metric_name -> value

        Returns:
            List of all detected anomalies
        """
        all_anomalies = []

        # Z-Score detection (per metric)
        for metric, value in metrics.items():
            if value is not None:
                result = self.zscore.detect(metric, value)
                if result:
                    all_anomalies.append(result)

        # Rolling mean detection (per metric)
        for metric, value in metrics.items():
            if value is not None:
                result = self.rolling_mean.detect(metric, value)
                if result:
                    all_anomalies.append(result)

        # Threshold detection (per metric)
        for metric, value in metrics.items():
            if value is not None:
                result = self.threshold.detect(metric, value)
                if result:
                    all_anomalies.append(result)

        # SPC detection (per metric)
        for metric, value in metrics.items():
            if value is not None:
                result = self.spc.detect(metric, value)
                if result:
                    all_anomalies.append(result)

        # Sort by severity (most severe first)
        severity_order = {
            AnomalySeverity.CRITICAL: 0,
            AnomalySeverity.ERROR: 1,
            AnomalySeverity.WARNING: 2,
            AnomalySeverity.INFO: 3,
        }
        all_anomalies.sort(key=lambda x: severity_order.get(x.severity, 4))

        if all_anomalies:
            logger.warning(
                "anomalies.detected",
                count=len(all_anomalies),
                metrics=list(set(a.metric for a in all_anomalies)),
            )

        return all_anomalies

    def detect_multivariate(self, data: np.ndarray, feature_names: list[str] | None = None) -> list[AnomalyResult]:
        """
        Run Isolation Forest on multivariate data.

        Args:
            data: 2D array of shape (n_samples, n_features)
            feature_names: Optional feature names

        Returns:
            List of AnomalyResult for detected anomalies
        """
        if not self.isolation_forest._fitted:
            logger.warning("isolation_forest.not_fitted")
            return []

        return self.isolation_forest.detect(data)

    def get_stats(self) -> dict:
        """Get detector statistics."""
        return {
            "isolation_forest_fitted": self.isolation_forest._fitted,
            "zscore_metrics_tracked": len(self.zscore._history),
            "rolling_metrics_tracked": len(self.rolling_mean._history),
            "spc_metrics_tracked": len(self.spc._history),
            "thresholds_configured": len(self.threshold._thresholds),
        }
