"""
Unit tests for anomaly detection module.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from ml.anomaly.detector import (
    AnomalyDetector,
    AnomalyResult,
    AnomalySeverity,
    AnomalyType,
    IsolationForestDetector,
    RollingMeanDetector,
    SPCDetector,
    ThresholdDetector,
    ZScoreDetector,
)


class TestAnomalyResult:
    """Tests for AnomalyResult class."""

    def test_create_result(self):
        result = AnomalyResult(
            metric="ac_power",
            value=100.0,
            score=0.8,
            threshold=0.5,
            severity=AnomalySeverity.WARNING,
            anomaly_type=AnomalyType.ZSCORE,
            description="Test anomaly",
        )
        assert result.metric == "ac_power"
        assert result.value == 100.0
        assert result.severity == AnomalySeverity.WARNING

    def test_to_dict(self):
        result = AnomalyResult(
            metric="temperature",
            value=85.0,
            score=0.9,
            threshold=3.0,
            severity=AnomalySeverity.ERROR,
            anomaly_type=AnomalyType.THRESHOLD,
            description="High temperature",
        )
        d = result.to_dict()
        assert d["metric"] == "temperature"
        assert d["severity"] == "error"
        assert d["anomaly_type"] == "threshold"
        assert "timestamp" in d


class TestIsolationForestDetector:
    """Tests for IsolationForestDetector."""

    def test_initialization(self):
        detector = IsolationForestDetector(contamination=0.1)
        assert detector.contamination == 0.1
        assert detector._fitted is False

    def test_fit_and_predict(self):
        detector = IsolationForestDetector(contamination=0.1)
        np.random.seed(42)
        data = np.random.randn(100, 3)

        detector.fit(data, feature_names=["power", "voltage", "current"])
        assert detector._fitted is True

        predictions = detector.predict(data[:5])
        assert len(predictions) == 5
        assert all(p in (-1, 1) for p in predictions)

    def test_score(self):
        detector = IsolationForestDetector()
        data = np.random.randn(100, 3)
        detector.fit(data)

        scores = detector.score(data[:5])
        assert len(scores) == 5
        assert all(isinstance(s, float) for s in scores)

    def test_detect(self):
        detector = IsolationForestDetector()
        data = np.random.randn(100, 3)
        detector.fit(data)

        results = detector.detect(data[:10])
        assert isinstance(results, list)

    def test_not_fitted_error(self):
        detector = IsolationForestDetector()
        with pytest.raises(RuntimeError, match="not fitted"):
            detector.predict(np.array([[1, 2, 3]]))


class TestZScoreDetector:
    """Tests for ZScoreDetector."""

    def test_initialization(self):
        detector = ZScoreDetector(threshold=3.0)
        assert detector.threshold == 3.0

    def test_no_anomaly_with_normal_data(self):
        detector = ZScoreDetector(threshold=3.0, min_samples=10)
        np.random.seed(42)
        for i in range(50):
            detector.update("power", 1000 + np.random.normal(0, 10))

        result = detector.detect("power", 1005)
        assert result is None

    def test_detect_anomaly(self):
        detector = ZScoreDetector(threshold=3.0, min_samples=10)
        np.random.seed(42)
        for i in range(50):
            detector.update("power", 1000 + np.random.normal(0, 10))

        result = detector.detect("power", 2000)
        assert result is not None
        assert result.severity in (AnomalySeverity.WARNING, AnomalySeverity.ERROR, AnomalySeverity.CRITICAL)

    def test_insufficient_data(self):
        detector = ZScoreDetector(min_samples=100)
        for i in range(5):
            detector.update("power", 1000)

        result = detector.detect("power", 2000)
        assert result is None


class TestRollingMeanDetector:
    """Tests for RollingMeanDetector."""

    def test_initialization(self):
        detector = RollingMeanDetector(window=20)
        assert detector.window == 20

    def test_no_anomaly_stable_data(self):
        detector = RollingMeanDetector(window=20, threshold=2.5)
        np.random.seed(42)
        for i in range(50):
            detector.update("power", 5000 + np.random.normal(0, 50))

        result = detector.detect("power", 5010)
        assert result is None

    def test_detect_sudden_change(self):
        detector = RollingMeanDetector(window=10, threshold=2.5)
        np.random.seed(42)
        for i in range(30):
            detector.update("power", 5000 + np.random.normal(0, 5))

        result = detector.detect("power", 10000)
        assert result is not None
        assert result.anomaly_type == AnomalyType.ROLLING_MEAN


class TestThresholdDetector:
    """Tests for ThresholdDetector."""

    def test_initialization(self):
        detector = ThresholdDetector()
        assert len(detector._thresholds) == 0

    def test_set_threshold(self):
        detector = ThresholdDetector()
        detector.set_threshold("temperature", min_value=-20, max_value=80)
        assert "temperature" in detector._thresholds

    def test_no_anomaly_within_range(self):
        detector = ThresholdDetector()
        detector.set_threshold("temperature", min_value=-20, max_value=80)

        result = detector.detect("temperature", 25)
        assert result is None

    def test_detect_below_min(self):
        detector = ThresholdDetector()
        detector.set_threshold("temperature", min_value=-20, max_value=80)

        result = detector.detect("temperature", -30)
        assert result is not None
        assert result.anomaly_type == AnomalyType.THRESHOLD

    def test_detect_above_max(self):
        detector = ThresholdDetector()
        detector.set_threshold("temperature", min_value=-20, max_value=80)

        result = detector.detect("temperature", 90)
        assert result is not None

    def test_no_threshold_configured(self):
        detector = ThresholdDetector()
        result = detector.detect("unknown_metric", 100)
        assert result is None


class TestSPCDetector:
    """Tests for SPCDetector."""

    def test_initialization(self):
        detector = SPCDetector(window=25, sigma=3.0)
        assert detector.window == 25
        assert detector.sigma == 3.0

    def test_no_anomaly_stable_process(self):
        detector = SPCDetector(window=20)
        np.random.seed(42)
        for i in range(50):
            detector.update("power", 5000 + np.random.normal(0, 50))

        result = detector.detect("power", 5010)
        assert result is None

    def test_detect_out_of_control(self):
        detector = SPCDetector(window=20)
        np.random.seed(42)
        for i in range(50):
            detector.update("power", 5000 + np.random.normal(0, 50))

        result = detector.detect("power", 7000)
        assert result is not None
        assert result.anomaly_type == AnomalyType.SPC


class TestAnomalyDetector:
    """Tests for combined AnomalyDetector."""

    def test_initialization(self):
        detector = AnomalyDetector()
        assert detector.isolation_forest is not None
        assert detector.zscore is not None
        assert detector.rolling_mean is not None
        assert detector.spc is not None
        assert detector.threshold is not None

    def test_detect_normal_data(self):
        detector = AnomalyDetector(zscore_threshold=3.0)
        np.random.seed(42)

        # Build up history with normal data
        for _ in range(50):
            detector.detect({
                "ac_power": 5000 + np.random.normal(0, 50),
                "temperature": 45 + np.random.normal(0, 2),
            })

        # Should detect few or no anomalies
        result = detector.detect({
            "ac_power": 5005,
            "temperature": 46,
        })
        assert isinstance(result, list)

    def test_detect_anomalous_data(self):
        detector = AnomalyDetector(zscore_threshold=2.0)
        np.random.seed(42)

        # Build up history
        for _ in range(50):
            detector.detect({"ac_power": 5000 + np.random.normal(0, 50)})

        # Now send very different value
        result = detector.detect({"ac_power": 15000})
        assert len(result) > 0
        # Check that at least one anomaly has non-INFO severity
        assert any(a.severity != AnomalySeverity.INFO for a in result)

    def test_get_stats(self):
        detector = AnomalyDetector()
        stats = detector.get_stats()
        assert "isolation_forest_fitted" in stats
        assert "zscore_metrics_tracked" in stats

    def test_fit_isolation_forest(self):
        detector = AnomalyDetector()
        data = np.random.randn(100, 3)
        detector.fit_isolation_forest(data, ["power", "voltage", "current"])
        assert detector.isolation_forest._fitted is True
