"""
Tests for Phase 5: Performance Scoring.

Tests calculator, benchmarking, and scoring.
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from src.ml.performance.calculator import PerformanceCalculator, PerformanceScore
from src.ml.performance.benchmark import PerformanceBenchmark, BenchmarkResult


class TestPerformanceCalculator:
    """Tests for PerformanceCalculator."""

    def test_initialization(self):
        calc = PerformanceCalculator()
        assert calc.nominal_power == 5000
        assert calc.degradation_rate == 0.005

    def test_initialization_custom(self):
        calc = PerformanceCalculator(nominal_power=10000, degradation_rate=0.01)
        assert calc.nominal_power == 10000
        assert calc.degradation_rate == 0.01

    def test_add_sample(self):
        calc = PerformanceCalculator()
        calc.add_sample("INV001", {"ac_power": 5000, "temperature": 25})

        history = calc.get_history("INV001")
        assert len(history) == 1
        assert history[0]["ac_power"] == 5000

    def test_add_multiple_samples(self):
        calc = PerformanceCalculator()
        for i in range(10):
            calc.add_sample("INV001", {
                "ac_power": 5000 + i * 100,
                "temperature": 25 + i,
                "status": "running",
            })

        history = calc.get_history("INV001")
        assert len(history) == 10

    def test_calculate_insufficient_data(self):
        calc = PerformanceCalculator()
        for i in range(5):
            calc.add_sample("INV001", {"ac_power": 5000})

        score = calc.calculate("INV001")
        assert score is None

    def test_calculate_no_data(self):
        calc = PerformanceCalculator()
        score = calc.calculate("INV001")
        assert score is None

    def test_calculate_normal_data(self):
        calc = PerformanceCalculator()
        for i in range(48):
            calc.add_sample("INV001", {
                "ac_power": 5000 + np.random.normal(0, 100),
                "temperature": 25 + np.random.normal(0, 2),
                "status": "running",
                "ac_energy": 5000,
            })

        score = calc.calculate("INV001", window_hours=24)

        assert score is not None
        assert isinstance(score, PerformanceScore)
        assert score.inverter_id == "INV001"
        assert 0 <= score.performance_ratio <= 120
        assert 0 <= score.calendar_energy_factor <= 120
        assert 0 <= score.availability <= 100
        assert 0 <= score.efficiency <= 100
        assert 0 <= score.overall_score <= 100

    def test_calculate_availability(self):
        calc = PerformanceCalculator()

        # All running
        for i in range(24):
            calc.add_sample("INV001", {"ac_power": 5000, "status": "running"})

        score = calc.calculate("INV001", window_hours=24)
        assert score.availability == 100.0

        # Some faults
        calc.clear_history("INV001")
        for i in range(24):
            status = "fault" if i < 6 else "running"
            calc.add_sample("INV001", {"ac_power": 5000, "status": status})

        score = calc.calculate("INV001", window_hours=24)
        assert score.availability == 75.0  # 18/24

    def test_calculate_efficiency_with_dc_power(self):
        calc = PerformanceCalculator()
        for i in range(24):
            calc.add_sample("INV001", {
                "ac_power": 4800,
                "dc_power": 5000,
                "status": "running",
            })

        score = calc.calculate("INV001", window_hours=24)
        assert score.efficiency == pytest.approx(96.0, abs=0.1)

    def test_calculate_efficiency_from_temperature(self):
        calc = PerformanceCalculator()
        for i in range(24):
            calc.add_sample("INV001", {
                "ac_power": 5000,
                "temperature": 25,
                "status": "running",
            })

        score = calc.calculate("INV001", window_hours=24)
        # At 25°C, efficiency should be ~96%
        assert 90 <= score.efficiency <= 100

    def test_score_to_grade(self):
        calc = PerformanceCalculator()

        assert calc._score_to_grade(98) == "A+"
        assert calc._score_to_grade(92) == "A"
        assert calc._score_to_grade(87) == "B+"
        assert calc._score_to_grade(82) == "B"
        assert calc._score_to_grade(77) == "C+"
        assert calc._score_to_grade(72) == "C"
        assert calc._score_to_grade(65) == "D"
        assert calc._score_to_grade(50) == "F"

    def test_set_baseline(self):
        calc = PerformanceCalculator()
        calc.set_baseline("INV001", {
            "installation_date": "2023-01-01T00:00:00+00:00",
        })

        assert "INV001" in calc._baseline

    def test_clear_history(self):
        calc = PerformanceCalculator()
        calc.add_sample("INV001", {"ac_power": 5000})
        calc.add_sample("INV002", {"ac_power": 6000})

        calc.clear_history("INV001")

        assert len(calc.get_history("INV001")) == 0
        assert len(calc.get_history("INV002")) == 1

    def test_get_stats(self):
        calc = PerformanceCalculator()
        calc.add_sample("INV001", {"ac_power": 5000})

        stats = calc.get_stats()
        assert stats["inverters_tracked"] == 1
        assert stats["total_samples"] == 1


class TestPerformanceScore:
    """Tests for PerformanceScore."""

    def test_create_score(self):
        score = PerformanceScore(
            inverter_id="INV001",
            performance_ratio=95.0,
            calendar_energy_factor=90.0,
            availability=99.0,
            efficiency=96.0,
            overall_score=94.0,
            grade="A",
        )

        assert score.inverter_id == "INV001"
        assert score.overall_score == 94.0
        assert score.grade == "A"

    def test_to_dict(self):
        score = PerformanceScore(
            inverter_id="INV001",
            performance_ratio=95.0,
            calendar_energy_factor=90.0,
            availability=99.0,
            efficiency=96.0,
            overall_score=94.0,
            grade="A",
            details={"mean_power": 5000},
        )

        result = score.to_dict()

        assert result["inverter_id"] == "INV001"
        assert result["overall_score"] == 94.0
        assert result["grade"] == "A"
        assert result["details"]["mean_power"] == 5000


class TestPerformanceBenchmark:
    """Tests for PerformanceBenchmark."""

    def test_initialization(self):
        bench = PerformanceBenchmark()
        assert bench.peer_group_key == "model"

    def test_initialization_custom(self):
        bench = PerformanceBenchmark(peer_group_key="capacity")
        assert bench.peer_group_key == "capacity"

    def test_add_inverter_score(self):
        bench = PerformanceBenchmark()
        bench.add_inverter_score("INV001", {
            "overall_score": 90,
            "performance_ratio": 95,
        }, peer_group="sunny")

        stats = bench.get_stats()
        assert stats["fleet_size"] == 1

    def test_benchmark_single_inverter(self):
        bench = PerformanceBenchmark()
        bench.add_inverter_score("INV001", {
            "overall_score": 90,
            "performance_ratio": 95,
        }, peer_group="sunny")

        result = bench.benchmark("INV001")

        assert result is not None
        assert isinstance(result, BenchmarkResult)
        assert result.inverter_id == "INV001"
        assert result.fleet_percentile == 50.0  # Single inverter = median
        assert result.vs_fleet_avg == 0.0

    def test_benchmark_multiple_inverters(self):
        bench = PerformanceBenchmark()
        scores = [
            ("INV001", 80, "sunny"),
            ("INV002", 90, "sunny"),
            ("INV003", 85, "fronius"),
            ("INV004", 95, "sunny"),
            ("INV005", 70, "fronius"),
        ]

        for inv_id, score, group in scores:
            bench.add_inverter_score(inv_id, {
                "overall_score": score,
                "performance_ratio": score + 5,
            }, peer_group=group)

        result = bench.benchmark("INV002")

        assert result is not None
        # INV002 (90) should be ranked higher than most
        assert result.fleet_percentile > 50
        assert result.peer_group == "sunny"

    def test_fleet_stats(self):
        bench = PerformanceBenchmark()
        bench.add_inverter_score("INV001", {"overall_score": 80})
        bench.add_inverter_score("INV002", {"overall_score": 90})

        stats = bench.get_fleet_stats()

        assert stats["total_inverters"] == 2
        assert stats["fleet_mean"] == 85.0
        assert stats["fleet_min"] == 80.0
        assert stats["fleet_max"] == 90.0

    def test_peer_group_stats(self):
        bench = PerformanceBenchmark()
        bench.add_inverter_score("INV001", {"overall_score": 80}, peer_group="sunny")
        bench.add_inverter_score("INV002", {"overall_score": 90}, peer_group="sunny")
        bench.add_inverter_score("INV003", {"overall_score": 85}, peer_group="fronius")

        stats = bench.get_peer_group_stats("sunny")

        assert stats["count"] == 2
        assert stats["mean"] == 85.0

    def test_peer_group_not_found(self):
        bench = PerformanceBenchmark()
        stats = bench.get_peer_group_stats("nonexistent")

        assert stats["count"] == 0

    def test_benchmark_unknown_inverter(self):
        bench = PerformanceBenchmark()
        result = bench.benchmark("UNKNOWN")

        assert result is None

    def test_historical_comparison(self):
        bench = PerformanceBenchmark()

        # Add historical scores
        for i in range(10):
            bench.add_inverter_score("INV001", {
                "overall_score": 80 + i,
            }, peer_group="sunny")

        result = bench.benchmark("INV001")

        assert result is not None
        # Should compare to historical average
        assert result.vs_historical != 0

    def test_get_stats(self):
        bench = PerformanceBenchmark()
        bench.add_inverter_score("INV001", {"overall_score": 80}, peer_group="sunny")
        bench.add_inverter_score("INV002", {"overall_score": 90}, peer_group="fronius")

        stats = bench.get_stats()

        assert stats["fleet_size"] == 2
        assert stats["peer_groups"] == 2


class TestBenchmarkResult:
    """Tests for BenchmarkResult."""

    def test_create_result(self):
        result = BenchmarkResult(
            inverter_id="INV001",
            overall_rank=85.0,
            fleet_percentile=75.0,
            vs_fleet_avg=5.0,
            vs_peer_avg=3.0,
            vs_historical=2.0,
            peer_group="sunny",
        )

        assert result.inverter_id == "INV001"
        assert result.fleet_percentile == 75.0
        assert result.peer_group == "sunny"

    def test_to_dict(self):
        result = BenchmarkResult(
            inverter_id="INV001",
            overall_rank=85.0,
            fleet_percentile=75.0,
            vs_fleet_avg=5.0,
            vs_peer_avg=3.0,
            vs_historical=2.0,
            peer_group="sunny",
            metrics={"overall_score": 90},
        )

        result_dict = result.to_dict()

        assert result_dict["inverter_id"] == "INV001"
        assert result_dict["fleet_percentile"] == 75.0
        assert result_dict["metrics"]["overall_score"] == 90
