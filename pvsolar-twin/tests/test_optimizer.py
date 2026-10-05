"""Testes do optimizer do pvSolar Digital Twin."""

import pytest
from src.core.config import (
    DegradationConfig,
    FinancialConfig,
    OptimizationTarget,
    PanelConfig,
    PlantConfig,
)
from src.optimizer.optimizer import OptimizationResult, Optimizer


class TestOptimizer:
    def test_create_optimizer(self):
        o = Optimizer()
        assert o.panel.rated_power_w == 400.0

    def test_optimize_tilt(self):
        o = Optimizer()
        result = o.optimize_tilt(1000.0)
        assert result.optimal_tilt >= 0
        assert result.optimal_tilt <= 60
        assert len(o.results) == 1

    def test_optimize_tilt_gain(self):
        o = Optimizer()
        result = o.optimize_tilt(1000.0, tilt_range=(0, 45), step=5)
        assert isinstance(result.energy_gain_percent, float)

    def test_optimize_panels(self):
        o = Optimizer()
        result = o.optimize_panel_count(5.0, max_panels=300)
        assert result.optimal_num_panels > 0
        assert len(o.results) == 1

    def test_optimize_panels_with_budget(self):
        o = Optimizer()
        result = o.optimize_panel_count(5.0, max_panels=500, budget=100000)
        assert result.optimal_num_panels > 0

    def test_calculate_roi(self):
        o = Optimizer()
        roi = o.calculate_roi(100000.0, 0.08)
        assert "roi_percent" in roi
        assert "payback_years" in roi
        assert "npv" in roi
        assert roi["capex"] == 500000.0

    def test_calculate_roi_positive(self):
        o = Optimizer()
        roi = o.calculate_roi(200000.0, 0.10)
        assert roi["roi_percent"] > 0

    def test_get_result(self):
        o = Optimizer()
        o.optimize_tilt(1000.0)
        result = o.get_result()
        assert result is not None

    def test_get_result_none(self):
        o = Optimizer()
        assert o.get_result() is None

    def test_get_all_results(self):
        o = Optimizer()
        o.optimize_tilt(1000.0)
        o.optimize_panel_count(5.0)
        results = o.get_all_results()
        assert len(results) == 2

    def test_get_statistics(self):
        o = Optimizer()
        o.optimize_tilt(1000.0)
        stats = o.get_statistics()
        assert stats["total_optimizations"] == 1

    def test_clear(self):
        o = Optimizer()
        o.optimize_tilt(1000.0)
        count = o.clear()
        assert count == 1
        assert len(o.results) == 0


class TestOptimizationResult:
    def test_to_dict(self):
        r = OptimizationResult(
            target=OptimizationTarget.ENERGY,
            optimal_tilt=25.0,
            optimal_num_panels=200,
        )
        d = r.to_dict()
        assert d["target"] == "energy"
        assert d["optimal_tilt"] == 25.0
        assert d["optimal_num_panels"] == 200
