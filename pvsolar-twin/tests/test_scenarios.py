"""Testes do scenario_engine do pvSolar Digital Twin."""

import pytest
from src.core.config import ScenarioConfig, ScenarioType
from src.scenarios.scenario_engine import ScenarioEngine, ScenarioResult


class TestScenarioEngine:
    def test_create_engine(self):
        e = ScenarioEngine()
        assert len(e.scenarios) == 0

    def test_add_scenario(self):
        e = ScenarioEngine()
        s = ScenarioConfig(name="test")
        e.add_scenario(s)
        assert len(e.scenarios) == 1

    def test_remove_scenario(self):
        e = ScenarioEngine()
        s = ScenarioConfig(name="test")
        e.add_scenario(s)
        assert e.remove_scenario("test") is True
        assert len(e.scenarios) == 0

    def test_remove_nonexistent(self):
        e = ScenarioEngine()
        assert e.remove_scenario("nope") is False

    def test_get_scenario(self):
        e = ScenarioEngine()
        s = ScenarioConfig(name="test")
        e.add_scenario(s)
        found = e.get_scenario("test")
        assert found is not None
        assert found.name == "test"

    def test_get_scenario_none(self):
        e = ScenarioEngine()
        assert e.get_scenario("nope") is None

    def test_evaluate_scenario(self):
        e = ScenarioEngine()
        s = ScenarioConfig(name="optimistic", irradiance_factor=1.1)
        result = e.evaluate_scenario(s, 1000.0, 0.08)
        assert result.scenario_energy_kwh > 1000.0
        assert result.energy_delta_kwh > 0

    def test_evaluate_scenario_pessimistic(self):
        e = ScenarioEngine()
        s = ScenarioConfig(name="pessimistic", irradiance_factor=0.8)
        result = e.evaluate_scenario(s, 1000.0, 0.08)
        assert result.scenario_energy_kwh < 1000.0

    def test_evaluate_all(self):
        e = ScenarioEngine()
        e.add_scenario(ScenarioConfig(name="s1", irradiance_factor=1.1))
        e.add_scenario(ScenarioConfig(name="s2", irradiance_factor=0.9))
        results = e.evaluate_all(1000.0, 0.08)
        assert len(results) == 2

    def test_compare_scenarios(self):
        e = ScenarioEngine()
        e.add_scenario(ScenarioConfig(name="s1", irradiance_factor=1.1))
        e.add_scenario(ScenarioConfig(name="s2", irradiance_factor=0.9))
        e.evaluate_all(1000.0, 0.08)
        comparison = e.compare_scenarios()
        assert comparison["total_scenarios"] == 2

    def test_compare_empty(self):
        e = ScenarioEngine()
        assert e.compare_scenarios() == {}

    def test_get_result(self):
        e = ScenarioEngine()
        s = ScenarioConfig(name="test")
        result = e.evaluate_scenario(s, 1000.0, 0.08)
        found = e.get_result(result.id)
        assert found is not None
        assert found.id == result.id

    def test_get_result_none(self):
        e = ScenarioEngine()
        assert e.get_result("nope") is None

    def test_get_results_by_type(self):
        e = ScenarioEngine()
        e.evaluate_scenario(
            ScenarioConfig(name="s1", type=ScenarioType.WHAT_IF), 1000.0, 0.08
        )
        results = e.get_results_by_type(ScenarioType.WHAT_IF)
        assert len(results) == 1

    def test_get_statistics(self):
        e = ScenarioEngine()
        e.add_scenario(ScenarioConfig(name="s1"))
        stats = e.get_statistics()
        assert stats["total_scenarios"] == 1

    def test_clear(self):
        e = ScenarioEngine()
        e.add_scenario(ScenarioConfig(name="s1"))
        e.evaluate_scenario(ScenarioConfig(name="s1"), 1000.0, 0.08)
        count = e.clear()
        assert count == 2
        assert len(e.scenarios) == 0
        assert len(e.results) == 0


class TestScenarioResult:
    def test_to_dict(self):
        r = ScenarioResult(name="test", base_energy_kwh=1000.0)
        d = r.to_dict()
        assert d["name"] == "test"
        assert d["base_energy_kwh"] == 1000.0
