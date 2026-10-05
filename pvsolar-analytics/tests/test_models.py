"""
Unit tests for storage models.
"""

import pytest
from datetime import datetime, timezone

from storage.models import (
    Base,
    Telemetry,
    Anomaly,
    MaintenancePrediction,
    EnergyForecast,
    PerformanceScore,
    Alert,
    Inverter,
)


class TestTelemetryModel:
    """Tests for Telemetry model."""

    def test_create_telemetry(self):
        telemetry = Telemetry(
            time=datetime.now(timezone.utc),
            inverter_id="inv-001",
            ac_power=5000.0,
            temperature=42.5,
            status="running",
        )
        assert telemetry.inverter_id == "inv-001"
        assert telemetry.ac_power == 5000.0
        assert telemetry.temperature == 42.5
        assert telemetry.status == "running"

    def test_telemetry_defaults(self):
        telemetry = Telemetry(inverter_id="inv-001")
        assert telemetry.ac_power is None
        assert telemetry.temperature is None
        assert telemetry.fault_code is None


class TestAnomalyModel:
    """Tests for Anomaly model."""

    def test_create_anomaly(self):
        anomaly = Anomaly(
            time=datetime.now(timezone.utc),
            inverter_id="inv-001",
            metric="ac_power",
            value=100.0,
            score=0.95,
            threshold=0.8,
            severity="warning",
            description="Abnormally low power output",
        )
        assert anomaly.inverter_id == "inv-001"
        assert anomaly.metric == "ac_power"
        assert anomaly.severity == "warning"


class TestMaintenancePredictionModel:
    """Tests for MaintenancePrediction model."""

    def test_create_prediction(self):
        prediction = MaintenancePrediction(
            time=datetime.now(timezone.utc),
            inverter_id="inv-001",
            failure_prob_7d=0.1,
            failure_prob_30d=0.3,
            failure_prob_90d=0.6,
            risk_level="medium",
            recommended_action="Schedule inspection",
        )
        assert prediction.inverter_id == "inv-001"
        assert prediction.failure_prob_30d == 0.3
        assert prediction.risk_level == "medium"


class TestEnergyForecastModel:
    """Tests for EnergyForecast model."""

    def test_create_forecast(self):
        forecast = EnergyForecast(
            time=datetime.now(timezone.utc),
            inverter_id="inv-001",
            forecast_horizon="24h",
            predicted_power=4500.0,
            confidence_low=4000.0,
            confidence_high=5000.0,
        )
        assert forecast.inverter_id == "inv-001"
        assert forecast.forecast_horizon == "24h"
        assert forecast.predicted_power == 4500.0


class TestPerformanceScoreModel:
    """Tests for PerformanceScore model."""

    def test_create_score(self):
        score = PerformanceScore(
            time=datetime.now(timezone.utc),
            inverter_id="inv-001",
            score=85.5,
            degradation_rate=0.02,
            capacity_ratio=0.95,
            mtbf_hours=8760.0,
        )
        assert score.inverter_id == "inv-001"
        assert score.score == 85.5
        assert score.mtbf_hours == 8760.0


class TestAlertModel:
    """Tests for Alert model."""

    def test_create_alert(self):
        alert = Alert(
            time=datetime.now(timezone.utc),
            inverter_id="inv-001",
            alert_type="over_temperature",
            severity="warning",
            message="Temperature exceeds 80°C",
        )
        assert alert.inverter_id == "inv-001"
        assert alert.alert_type == "over_temperature"
        # Note: acknowledged default is set by DB, not Python object
        assert alert.acknowledged is None or alert.acknowledged == 0


class TestInverterModel:
    """Tests for Inverter model."""

    def test_create_inverter(self):
        inverter = Inverter(
            id="inv-001",
            name="Fronius GEN24 6.0",
            driver="fronius",
            manufacturer="Fronius",
            model="GEN24 6.0 Plus",
        )
        assert inverter.id == "inv-001"
        assert inverter.name == "Fronius GEN24 6.0"
        # Note: status default is set by DB, not Python object
        assert inverter.status is None or inverter.status == "unknown"

    def test_inverter_defaults(self):
        inverter = Inverter(id="inv-001", name="Test", driver="sunspec")
        # Note: status default is set by DB, not Python object
        assert inverter.status is None or inverter.status == "unknown"
        assert inverter.manufacturer is None
        assert inverter.serial_number is None
