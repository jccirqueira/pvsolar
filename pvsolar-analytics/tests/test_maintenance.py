"""
Tests for Phase 3: Predictive Maintenance.

Tests feature extraction, model training, and prediction.
"""

import pytest
import numpy as np
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.ml.maintenance.features import MaintenanceFeatureExtractor
from src.ml.maintenance.predictor import (
    MaintenancePredictor,
    MaintenancePrediction,
    RiskLevel,
)


class TestMaintenanceFeatureExtractor:
    """Tests for MaintenanceFeatureExtractor."""

    def test_initialization(self):
        extractor = MaintenanceFeatureExtractor()
        assert extractor.window_size == 100

    def test_initialization_custom_window(self):
        extractor = MaintenanceFeatureExtractor(window_size=200)
        assert extractor.window_size == 200

    def test_add_sample(self):
        extractor = MaintenanceFeatureExtractor()
        extractor.add_sample("INV001", {"ac_power": 5000, "temperature": 25.0})

        history = extractor.get_history("INV001")
        assert len(history) == 1
        assert history[0]["ac_power"] == 5000

    def test_add_multiple_samples(self):
        extractor = MaintenanceFeatureExtractor()
        for i in range(10):
            extractor.add_sample("INV001", {"ac_power": 5000 + i, "temperature": 25 + i})

        history = extractor.get_history("INV001")
        assert len(history) == 10

    def test_extract_features_insufficient_data(self):
        extractor = MaintenanceFeatureExtractor()
        for i in range(5):
            extractor.add_sample("INV001", {"ac_power": 5000})

        features = extractor.extract_features("INV001")
        assert features is None

    def test_extract_features_no_data(self):
        extractor = MaintenanceFeatureExtractor()
        features = extractor.extract_features("INV001")
        assert features is None

    def test_extract_features_normal_data(self):
        extractor = MaintenanceFeatureExtractor()
        for i in range(50):
            extractor.add_sample("INV001", {
                "ac_power": 5000 + np.random.normal(0, 100),
                "temperature": 25 + np.random.normal(0, 2),
                "efficiency": 0.95 + np.random.normal(0, 0.01),
                "ac_frequency": 60 + np.random.normal(0, 0.1),
            })

        features = extractor.extract_features("INV001")

        assert features is not None
        assert "ac_power_mean" in features
        assert "ac_power_std" in features
        assert "ac_power_min" in features
        assert "ac_power_max" in features

    def test_extract_features_trend(self):
        extractor = MaintenanceFeatureExtractor()
        for i in range(50):
            # Downward trend
            extractor.add_sample("INV001", {
                "ac_power": 5000 - i * 10,
                "temperature": 25,
            })

        features = extractor.extract_features("INV001")

        assert features is not None
        assert "ac_power_slope" in features
        # Slope should be negative (downward trend)
        assert features["ac_power_slope"] < 0

    def test_extract_features_stability(self):
        extractor = MaintenanceFeatureExtractor()
        # Very stable data
        for i in range(50):
            extractor.add_sample("INV001", {
                "ac_power": 5000 + np.random.normal(0, 0.001),
                "temperature": 25,
            })

        features = extractor.extract_features("INV001")

        assert features is not None
        assert "ac_power_cv" in features
        # CV should be very small for stable data
        assert features["ac_power_cv"] < 0.01

    def test_clear_history(self):
        extractor = MaintenanceFeatureExtractor()
        extractor.add_sample("INV001", {"ac_power": 5000})
        extractor.add_sample("INV002", {"ac_power": 6000})

        extractor.clear_history("INV001")

        assert len(extractor.get_history("INV001")) == 0
        assert len(extractor.get_history("INV002")) == 1

    def test_clear_all_history(self):
        extractor = MaintenanceFeatureExtractor()
        extractor.add_sample("INV001", {"ac_power": 5000})
        extractor.add_sample("INV002", {"ac_power": 6000})

        extractor.clear_history()

        assert len(extractor.get_history("INV001")) == 0
        assert len(extractor.get_history("INV002")) == 0

    def test_get_stats(self):
        extractor = MaintenanceFeatureExtractor()
        extractor.add_sample("INV001", {"ac_power": 5000})
        extractor.add_sample("INV002", {"ac_power": 6000})

        stats = extractor.get_stats()
        assert stats["inverters_tracked"] == 2
        assert stats["total_samples"] == 2

    def test_window_limit(self):
        extractor = MaintenanceFeatureExtractor(window_size=20)
        for i in range(100):
            extractor.add_sample("INV001", {"ac_power": 5000 + i})

        history = extractor.get_history("INV001")
        # Should keep more than window_size (up to 3x)
        assert len(history) <= 60


class TestMaintenancePredictor:
    """Tests for MaintenancePredictor."""

    def test_initialization(self):
        predictor = MaintenancePredictor()
        assert predictor.is_fitted is False
        assert predictor.model_version == "1.0.0"

    def test_initialization_custom_version(self):
        predictor = MaintenancePredictor(model_version="2.0.0")
        assert predictor.model_version == "2.0.0"

    def test_predict_not_fitted(self):
        predictor = MaintenancePredictor()
        prediction = predictor.predict({"ac_power_mean": 5000}, "INV001")

        assert prediction.risk_level == RiskLevel.LOW
        assert prediction.failure_prob_7d < 0.1
        assert prediction.model_version == "untrained"

    def test_fit_insufficient_samples(self):
        predictor = MaintenancePredictor()
        X = np.random.rand(10, 5)
        y = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 1])

        with pytest.raises(ValueError, match="Need at least 20 samples"):
            predictor.fit(X, y, y, y)

    def test_fit_no_positive_samples(self):
        predictor = MaintenancePredictor()
        X = np.random.rand(30, 5)
        y_all_negative = np.zeros(30)

        predictor.fit(X, y_all_negative, y_all_negative, y_all_negative)

        assert predictor.is_fitted is True
        # 7d model should not be trained (no positive samples)
        assert "7d" not in predictor._models

    def test_fit_normal_data(self):
        np.random.seed(42)
        predictor = MaintenancePredictor()

        n_samples = 100
        X = np.random.rand(n_samples, 10)
        y_7d = (X[:, 0] > 0.8).astype(int)
        y_30d = (X[:, 1] > 0.6).astype(int)
        y_90d = (X[:, 2] > 0.4).astype(int)

        predictor.fit(X, y_7d, y_30d, y_90d, feature_names=[f"f{i}" for i in range(10)])

        assert predictor.is_fitted is True
        assert "30d" in predictor._models

    def test_predict_normal_features(self):
        np.random.seed(42)
        predictor = self._create_trained_predictor()

        features = {f"f{i}": np.random.rand() for i in range(10)}
        prediction = predictor.predict(features, "INV001")

        assert isinstance(prediction, MaintenancePrediction)
        assert prediction.inverter_id == "INV001"
        assert 0 <= prediction.failure_prob_7d <= 1
        assert 0 <= prediction.failure_prob_30d <= 1
        assert 0 <= prediction.failure_prob_90d <= 1
        assert prediction.risk_level in list(RiskLevel)

    def test_predict_anomalous_features(self):
        predictor = self._create_trained_predictor()

        # Features that indicate high risk
        features = {f"f{i}": 0.95 for i in range(10)}
        prediction = predictor.predict(features, "INV001")

        assert prediction.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    def test_predict_safe_features(self):
        predictor = self._create_trained_predictor()

        # Features that indicate low risk
        features = {f"f{i}": 0.05 for i in range(10)}
        prediction = predictor.predict(features, "INV001")

        assert prediction.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]

    def test_get_feature_importance(self):
        predictor = self._create_trained_predictor()

        importances = predictor.get_feature_importance()

        assert len(importances) == 10
        assert all(isinstance(v, float) for v in importances.values())
        assert sum(importances.values()) == pytest.approx(1.0, abs=0.01)

    def test_get_stats(self):
        predictor = self._create_trained_predictor()

        stats = predictor.get_stats()

        assert stats["fitted"] is True
        assert "models" in stats
        assert "n_features" in stats
        assert stats["n_features"] == 10

    def _create_trained_predictor(self) -> MaintenancePredictor:
        """Helper to create a trained predictor."""
        np.random.seed(42)
        predictor = MaintenancePredictor()

        n_samples = 100
        X = np.random.rand(n_samples, 10)
        y_7d = (X[:, 0] > 0.8).astype(int)
        y_30d = (X[:, 1] > 0.6).astype(int)
        y_90d = (X[:, 2] > 0.4).astype(int)

        predictor.fit(X, y_7d, y_30d, y_90d, feature_names=[f"f{i}" for i in range(10)])

        return predictor


class TestMaintenancePrediction:
    """Tests for MaintenancePrediction dataclass."""

    def test_create_prediction(self):
        prediction = MaintenancePrediction(
            inverter_id="INV001",
            failure_prob_7d=0.05,
            failure_prob_30d=0.15,
            failure_prob_90d=0.3,
            risk_level=RiskLevel.LOW,
            recommended_action="Continue monitoring",
        )

        assert prediction.inverter_id == "INV001"
        assert prediction.failure_prob_7d == 0.05
        assert prediction.risk_level == RiskLevel.LOW

    def test_to_dict(self):
        prediction = MaintenancePrediction(
            inverter_id="INV001",
            failure_prob_7d=0.05,
            failure_prob_30d=0.15,
            failure_prob_90d=0.3,
            risk_level=RiskLevel.MEDIUM,
            recommended_action="Schedule maintenance",
            confidence=0.85,
            top_features=[{"feature": "f1", "importance": 0.3}],
        )

        result = prediction.to_dict()

        assert result["inverter_id"] == "INV001"
        assert result["failure_prob_7d"] == 0.05
        assert result["risk_level"] == "medium"
        assert result["confidence"] == 0.85
        assert len(result["top_features"]) == 1

    def test_risk_levels(self):
        for level in RiskLevel:
            prediction = MaintenancePrediction(
                inverter_id="INV001",
                failure_prob_7d=0.0,
                failure_prob_30d=0.0,
                failure_prob_90d=0.0,
                risk_level=level,
                recommended_action="Test",
            )
            assert prediction.risk_level.value == level.value


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_levels_exist(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_count(self):
        assert len(RiskLevel) == 4
