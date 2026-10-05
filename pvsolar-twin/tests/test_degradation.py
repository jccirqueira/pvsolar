"""Testes do degradation_engine do pvSolar Digital Twin."""

import pytest

from src.core.config import DegradationConfig, DegradationModel
from src.degradation.degradation_engine import (
    DegradationEngine,
    DegradationForecast,
    DegradationPoint,
)


class TestDegradationEngine:
    def test_create_engine(self):
        e = DegradationEngine()
        assert e.config.annual_rate == 0.005

    def test_linear_degradation(self):
        config = DegradationConfig(model=DegradationModel.LINEAR, annual_rate=0.01)
        e = DegradationEngine(config)
        factor = e.get_degradation_factor(10)
        assert factor < 1.0
        assert factor > 0.8

    def test_exponential_degradation(self):
        config = DegradationConfig(model=DegradationModel.EXPONENTIAL, annual_rate=0.01)
        e = DegradationEngine(config)
        factor = e.get_degradation_factor(10)
        assert factor < 1.0

    def test_logarithmic_degradation(self):
        config = DegradationConfig(model=DegradationModel.LOGARITHMIC, annual_rate=0.01)
        e = DegradationEngine(config)
        factor = e.get_degradation_factor(10)
        assert factor < 1.0

    def test_step_degradation(self):
        config = DegradationConfig(model=DegradationModel.STEP)
        e = DegradationEngine(config)
        factor = e.get_degradation_factor(5)
        assert 0.9 <= factor <= 1.0

    def test_year_1_penalty(self):
        config = DegradationConfig(year_1_penalty=0.05)
        e = DegradationEngine(config)
        factor = e.get_degradation_factor(1)
        assert factor < 1.0

    def test_generate_forecast(self):
        e = DegradationEngine()
        forecast = e.generate_forecast(25)
        assert len(forecast.points) == 26
        assert forecast.final_factor < 1.0
        assert forecast.total_loss_percent > 0

    def test_predict_power_at_year(self):
        e = DegradationEngine()
        power = e.predict_power_at_year(400.0, 10)
        assert power < 400.0
        assert power > 0

    def test_predict_energy_at_year(self):
        e = DegradationEngine()
        energy = e.predict_energy_at_year(100000.0, 10)
        assert energy < 100000.0
        assert energy > 0

    def test_calculate_remaining_useful_life(self):
        e = DegradationEngine()
        life = e.calculate_remaining_useful_life(0.8)
        assert life > 0
        assert life <= 25

    def test_record_measurement(self):
        e = DegradationEngine()
        e.record_measurement(5, 0.97)
        assert len(e.history) == 1

    def test_get_prediction_error(self):
        e = DegradationEngine()
        e.record_measurement(5, 0.97)
        error = e.get_prediction_error()
        assert error >= 0

    def test_get_forecast(self):
        e = DegradationEngine()
        e.generate_forecast(25)
        f = e.get_forecast()
        assert f is not None

    def test_get_forecast_none(self):
        e = DegradationEngine()
        assert e.get_forecast() is None

    def test_get_statistics(self):
        e = DegradationEngine()
        e.generate_forecast(25)
        stats = e.get_statistics()
        assert stats["forecasts_generated"] == 1

    def test_clear(self):
        e = DegradationEngine()
        e.generate_forecast(25)
        count = e.clear()
        assert count == 1
        assert len(e.forecasts) == 0


class TestDegradationForecast:
    def test_to_dict(self):
        f = DegradationForecast(annual_rate=0.005, warranty_years=25)
        d = f.to_dict()
        assert d["annual_rate"] == 0.005
        assert d["warranty_years"] == 25


class TestDegradationPoint:
    def test_create_point(self):
        p = DegradationPoint(year=5, factor=0.975)
        assert p.year == 5
        assert p.factor == 0.975
