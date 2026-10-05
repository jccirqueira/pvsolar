"""
Tests for Phase 4: Energy Forecasting.

Tests feature extraction, LSTM model, and forecasting.
"""

from datetime import UTC, datetime, timedelta, timezone

import numpy as np
from src.ml.forecast.features import ForecastFeatureExtractor
from src.ml.forecast.predictor import EnergyForecast, EnergyForecastPredictor


class TestForecastFeatureExtractor:
    """Tests for ForecastFeatureExtractor."""

    def test_initialization(self):
        extractor = ForecastFeatureExtractor()
        assert extractor.sequence_length == 24
        assert extractor.forecast_horizon == 24

    def test_initialization_custom(self):
        extractor = ForecastFeatureExtractor(sequence_length=48, forecast_horizon=12)
        assert extractor.sequence_length == 48
        assert extractor.forecast_horizon == 12

    def test_add_sample(self):
        extractor = ForecastFeatureExtractor()
        extractor.add_sample("INV001", {
            "ac_power": 5000,
            "temperature": 25.0,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        history = extractor.get_history("INV001")
        assert len(history) == 1
        assert history[0]["ac_power"] == 5000

    def test_add_multiple_samples(self):
        extractor = ForecastFeatureExtractor()
        for i in range(30):
            extractor.add_sample("INV001", {
                "ac_power": 5000 + i,
                "temperature": 25 + i * 0.1,
                "efficiency": 0.95,
                "timestamp": (datetime.now(UTC) + timedelta(hours=i)).isoformat(),
            })

        history = extractor.get_history("INV001")
        assert len(history) == 30

    def test_extract_features_insufficient_data(self):
        extractor = ForecastFeatureExtractor(sequence_length=24)
        for _i in range(10):
            extractor.add_sample("INV001", {"ac_power": 5000})

        features = extractor.extract_features("INV001")
        assert features is None

    def test_extract_features_no_data(self):
        extractor = ForecastFeatureExtractor()
        features = extractor.extract_features("INV001")
        assert features is None

    def test_extract_features_normal_data(self):
        extractor = ForecastFeatureExtractor(sequence_length=24)
        for i in range(48):
            extractor.add_sample("INV001", {
                "ac_power": 5000 + np.random.normal(0, 100),
                "temperature": 25 + np.random.normal(0, 2),
                "efficiency": 0.95 + np.random.normal(0, 0.01),
                "timestamp": (datetime.now(UTC) + timedelta(hours=i)).isoformat(),
            })

        features = extractor.extract_features("INV001")

        assert features is not None
        assert "hour_sin" in features
        assert "hour_cos" in features
        assert "day_of_week" in features
        assert "power_sequence" in features
        assert "temperature_sequence" in features
        assert len(features["power_sequence"]) == 24

    def test_extract_features_rolling_stats(self):
        extractor = ForecastFeatureExtractor(sequence_length=24)
        for i in range(48):
            extractor.add_sample("INV001", {
                "ac_power": 5000 + i * 10,
                "temperature": 25,
                "timestamp": (datetime.now(UTC) + timedelta(hours=i)).isoformat(),
            })

        features = extractor.extract_features("INV001")

        assert features is not None
        assert "power_rolling_mean_3" in features
        assert "power_rolling_mean_24" in features
        assert "power_rolling_std_24" in features

    def test_extract_features_lag(self):
        extractor = ForecastFeatureExtractor(sequence_length=24)
        for i in range(48):
            extractor.add_sample("INV001", {
                "ac_power": 5000 + i,
                "temperature": 25,
                "timestamp": (datetime.now(UTC) + timedelta(hours=i)).isoformat(),
            })

        features = extractor.extract_features("INV001")

        assert features is not None
        assert "power_lag_1" in features
        assert "power_lag_24" in features

    def test_extract_features_trend(self):
        extractor = ForecastFeatureExtractor(sequence_length=24)
        for i in range(48):
            # Downward trend
            extractor.add_sample("INV001", {
                "ac_power": 5000 - i * 10,
                "temperature": 25,
                "timestamp": (datetime.now(UTC) + timedelta(hours=i)).isoformat(),
            })

        features = extractor.extract_features("INV001")

        assert features is not None
        assert "power_slope" in features
        # Slope should be negative
        assert features["power_slope"] < 0

    def test_extract_features_temporal(self):
        extractor = ForecastFeatureExtractor(sequence_length=24)
        base_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)  # Saturday noon

        # Add 72 samples (3 days) to have enough history
        for i in range(72):
            extractor.add_sample("INV001", {
                "ac_power": 5000,
                "temperature": 25,
                "timestamp": (base_time + timedelta(hours=i)).isoformat(),
            })

        # Extract features at Sunday midnight (24 hours after Saturday noon)
        target = base_time + timedelta(hours=24)
        features = extractor.extract_features("INV001", target_time=target)

        assert features is not None
        # Saturday noon + 24h = Sunday, day_of_week = 6
        assert features["day_of_week"] == 6.0
        assert features["is_weekend"] == 1.0  # Sunday
        assert features["month"] == 6.0

    def test_clear_history(self):
        extractor = ForecastFeatureExtractor()
        extractor.add_sample("INV001", {"ac_power": 5000})
        extractor.add_sample("INV002", {"ac_power": 6000})

        extractor.clear_history("INV001")

        assert len(extractor.get_history("INV001")) == 0
        assert len(extractor.get_history("INV002")) == 1

    def test_get_stats(self):
        extractor = ForecastFeatureExtractor(sequence_length=48, forecast_horizon=12)
        extractor.add_sample("INV001", {"ac_power": 5000})

        stats = extractor.get_stats()
        assert stats["inverters_tracked"] == 1
        assert stats["total_samples"] == 1
        assert stats["sequence_length"] == 48
        assert stats["forecast_horizon"] == 12


class TestEnergyForecastPredictor:
    """Tests for EnergyForecastPredictor."""

    def test_initialization(self):
        predictor = EnergyForecastPredictor()
        assert predictor.is_fitted is False
        assert predictor.model_version == "1.0.0"
        assert predictor.sequence_length == 24
        assert predictor.forecast_horizon == 24

    def test_initialization_custom(self):
        predictor = EnergyForecastPredictor(
            model_version="2.0.0",
            sequence_length=48,
            forecast_horizon=12,
        )
        assert predictor.model_version == "2.0.0"
        assert predictor.sequence_length == 48
        assert predictor.forecast_horizon == 12

    def test_predict_not_fitted(self):
        predictor = EnergyForecastPredictor()
        features = {
            "power_sequence": np.random.rand(24).tolist(),
            "hour_sin": 0.5,
            "hour_cos": 0.8,
        }

        forecast = predictor.predict(features, "INV001")

        assert isinstance(forecast, EnergyForecast)
        assert forecast.inverter_id == "INV001"
        assert forecast.model_version == "untrained"
        assert len(forecast.hourly_forecast) == 24

    def test_fit_simple(self):
        predictor = EnergyForecastPredictor(forecast_horizon=12)
        n_samples = 50
        seq_len = 24
        n_features = 10

        X = np.random.rand(n_samples, seq_len, n_features)
        y = np.random.rand(n_samples, 12)

        predictor.fit(X, y, feature_names=[f"f{i}" for i in range(n_features)])

        assert predictor.is_fitted is True

    def test_predict_after_fit(self):
        predictor = EnergyForecastPredictor(forecast_horizon=12)
        n_samples = 50
        seq_len = 24
        n_features = 10

        X = np.random.rand(n_samples, seq_len, n_features)
        y = np.random.rand(n_samples, 12)

        predictor.fit(X, y, feature_names=[f"f{i}" for i in range(n_features)])

        features = {
            "power_sequence": np.random.rand(24),
            "temperature_sequence": np.random.rand(24) * 30,
            "efficiency_sequence": np.random.rand(24) * 0.2 + 0.8,
            "hour_sin": 0.5,
            "hour_cos": 0.8,
            "day_of_week": 3,
            "is_weekend": 0,
            "temp_mean": 25,
            "temp_std": 5,
            "power_rolling_mean_24": 5000,
            "power_rolling_std_24": 200,
            "power_slope": -10,
        }

        forecast = predictor.predict(features, "INV001")

        assert isinstance(forecast, EnergyForecast)
        assert forecast.inverter_id == "INV001"
        assert forecast.model_version == "1.0.0"
        assert len(forecast.hourly_forecast) == 12
        assert forecast.daily_forecast >= 0
        assert forecast.weekly_forecast >= 0
        assert 0 <= forecast.confidence <= 1

    def test_get_stats(self):
        predictor = EnergyForecastPredictor()
        stats = predictor.get_stats()

        assert stats["fitted"] is False
        assert stats["sequence_length"] == 24
        assert stats["forecast_horizon"] == 24

    def test_get_stats_fitted(self):
        predictor = EnergyForecastPredictor(forecast_horizon=12)
        n_samples = 50
        X = np.random.rand(n_samples, 24, 10)
        y = np.random.rand(n_samples, 12)

        predictor.fit(X, y)
        stats = predictor.get_stats()

        assert stats["fitted"] is True
        assert stats["model_type"] in ["torch", "simple"]


class TestEnergyForecast:
    """Tests for EnergyForecast dataclass."""

    def test_create_forecast(self):
        forecast = EnergyForecast(
            inverter_id="INV001",
            hourly_forecast=[100, 200, 300],
            daily_forecast=600,
            weekly_forecast=4200,
            confidence=0.85,
            forecast_start="2024-01-01T00:00:00",
            forecast_end="2024-01-02T00:00:00",
        )

        assert forecast.inverter_id == "INV001"
        assert forecast.hourly_forecast == [100, 200, 300]
        assert forecast.daily_forecast == 600
        assert forecast.confidence == 0.85

    def test_to_dict(self):
        forecast = EnergyForecast(
            inverter_id="INV001",
            hourly_forecast=[100, 200],
            daily_forecast=300,
            weekly_forecast=2100,
            confidence=0.9,
            forecast_start="2024-01-01T00:00:00",
            forecast_end="2024-01-02T00:00:00",
            model_version="1.0.0",
        )

        result = forecast.to_dict()

        assert result["inverter_id"] == "INV001"
        assert result["hourly_forecast"] == [100, 200]
        assert result["daily_forecast"] == 300
        assert result["model_version"] == "1.0.0"

    def test_forecast_horizons(self):
        """Test that forecast supports different horizons."""
        for horizon in [12, 24, 48, 168]:
            forecast = EnergyForecast(
                inverter_id="INV001",
                hourly_forecast=[0.0] * horizon,
                daily_forecast=0.0,
                weekly_forecast=0.0,
                confidence=0.5,
                forecast_start="2024-01-01T00:00:00",
                forecast_end="2024-01-01T00:00:00",
            )
            assert len(forecast.hourly_forecast) == horizon


class TestSimpleForecaster:
    """Tests for SimpleForecaster (fallback when PyTorch unavailable)."""

    def test_initialization(self):
        from src.ml.forecast.model import SimpleForecaster
        forecaster = SimpleForecaster(forecast_horizon=24)
        assert forecaster.forecast_horizon == 24

    def test_fit(self):
        from src.ml.forecast.model import SimpleForecaster
        forecaster = SimpleForecaster()
        values = [100 + i * 10 for i in range(48)]
        forecaster.fit(values)
        assert forecaster._fitted is True

    def test_predict(self):
        from src.ml.forecast.model import SimpleForecaster
        forecaster = SimpleForecaster(forecast_horizon=12)
        values = [100 + i * 10 for i in range(48)]
        forecaster.fit(values)

        predictions = forecaster.predict(values)

        assert len(predictions) == 12
        assert all(isinstance(p, (int, float)) for p in predictions)

    def test_predict_insufficient_data(self):
        from src.ml.forecast.model import SimpleForecaster
        forecaster = SimpleForecaster(forecast_horizon=24)
        values = [100, 200, 300]

        predictions = forecaster.predict(values)

        assert len(predictions) == 24
