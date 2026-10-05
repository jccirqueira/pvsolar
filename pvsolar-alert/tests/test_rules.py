"""Testes do rules_engine do pvSolar Alert."""

import pytest
from src.core.config import (
    AlertRuleConfig,
    AlertSeverity,
    RuleCondition,
)
from src.rules.rules_engine import RulesEngine


class TestRulesEngine:
    def test_create_engine(self):
        e = RulesEngine()
        assert len(e.rules) == 0

    def test_add_rule(self):
        e = RulesEngine()
        rule = AlertRuleConfig(id="r1", name="Test Rule")
        e.add_rule(rule)
        assert len(e.rules) == 1

    def test_remove_rule(self):
        e = RulesEngine()
        rule = AlertRuleConfig(id="r1", name="Test Rule")
        e.add_rule(rule)
        assert e.remove_rule("r1") is True
        assert len(e.rules) == 0

    def test_remove_nonexistent(self):
        e = RulesEngine()
        assert e.remove_rule("nope") is False

    def test_get_rule(self):
        e = RulesEngine()
        rule = AlertRuleConfig(id="r1", name="Test Rule")
        e.add_rule(rule)
        found = e.get_rule("r1")
        assert found is not None
        assert found.name == "Test Rule"

    def test_get_active_rules(self):
        e = RulesEngine()
        e.add_rule(AlertRuleConfig(id="r1", name="Active", enabled=True))
        e.add_rule(AlertRuleConfig(id="r2", name="Inactive", enabled=False))
        active = e.get_active_rules()
        assert len(active) == 1
        assert active[0].id == "r1"

    def test_evaluate_condition_eq(self):
        e = RulesEngine()
        c = RuleCondition(field="temp", operator="eq", value=50.0)
        assert e.evaluate_condition(c, {"temp": 50.0}) is True
        assert e.evaluate_condition(c, {"temp": 60.0}) is False

    def test_evaluate_condition_gt(self):
        e = RulesEngine()
        c = RuleCondition(field="temp", operator="gt", value=50.0)
        assert e.evaluate_condition(c, {"temp": 60.0}) is True
        assert e.evaluate_condition(c, {"temp": 40.0}) is False

    def test_evaluate_condition_gte(self):
        e = RulesEngine()
        c = RuleCondition(field="temp", operator="gte", value=50.0)
        assert e.evaluate_condition(c, {"temp": 50.0}) is True
        assert e.evaluate_condition(c, {"temp": 40.0}) is False

    def test_evaluate_condition_lt(self):
        e = RulesEngine()
        c = RuleCondition(field="temp", operator="lt", value=50.0)
        assert e.evaluate_condition(c, {"temp": 40.0}) is True
        assert e.evaluate_condition(c, {"temp": 60.0}) is False

    def test_evaluate_condition_lte(self):
        e = RulesEngine()
        c = RuleCondition(field="temp", operator="lte", value=50.0)
        assert e.evaluate_condition(c, {"temp": 50.0}) is True
        assert e.evaluate_condition(c, {"temp": 60.0}) is False

    def test_evaluate_condition_ne(self):
        e = RulesEngine()
        c = RuleCondition(field="status", operator="ne", value=1.0)
        assert e.evaluate_condition(c, {"status": 2}) is True
        assert e.evaluate_condition(c, {"status": 1}) is False

    def test_evaluate_condition_missing_field(self):
        e = RulesEngine()
        c = RuleCondition(field="missing", operator="eq", value=1.0)
        assert e.evaluate_condition(c, {}) is False

    def test_evaluate_rule_match(self):
        e = RulesEngine()
        rule = AlertRuleConfig(
            id="r1",
            name="High Temp",
            enabled=True,
            conditions=[
                RuleCondition(field="temp", operator="gt", value=50.0)
            ],
        )
        assert e.evaluate_rule(rule, {"temp": 60.0}) is True

    def test_evaluate_rule_no_match(self):
        e = RulesEngine()
        rule = AlertRuleConfig(
            id="r1",
            name="High Temp",
            enabled=True,
            conditions=[
                RuleCondition(field="temp", operator="gt", value=50.0)
            ],
        )
        assert e.evaluate_rule(rule, {"temp": 40.0}) is False

    def test_evaluate_rule_disabled(self):
        e = RulesEngine()
        rule = AlertRuleConfig(id="r1", name="Disabled", enabled=False)
        assert e.evaluate_rule(rule, {}) is False

    def test_evaluate_all(self):
        e = RulesEngine()
        e.add_rule(
            AlertRuleConfig(
                id="r1",
                name="High Temp",
                enabled=True,
                conditions=[RuleCondition(field="temp", operator="gt", value=50.0)],
                severity=AlertSeverity.HIGH,
            )
        )
        e.add_rule(
            AlertRuleConfig(
                id="r2",
                name="Low Battery",
                enabled=True,
                conditions=[RuleCondition(field="battery", operator="lt", value=20.0)],
                severity=AlertSeverity.CRITICAL,
            )
        )
        matches = e.evaluate_all({"temp": 60.0, "battery": 10.0})
        assert len(matches) == 2

    def test_get_rules_by_severity(self):
        e = RulesEngine()
        e.add_rule(AlertRuleConfig(id="r1", name="A", severity=AlertSeverity.HIGH))
        e.add_rule(AlertRuleConfig(id="r2", name="B", severity=AlertSeverity.LOW))
        high = e.get_rules_by_severity(AlertSeverity.HIGH)
        assert len(high) == 1

    def test_get_rules_count(self):
        e = RulesEngine()
        e.add_rule(AlertRuleConfig(id="r1", name="A", enabled=True))
        e.add_rule(AlertRuleConfig(id="r2", name="B", enabled=False))
        stats = e.get_rules_count()
        assert stats["total"] == 2
        assert stats["active"] == 1

    def test_update_rule(self):
        e = RulesEngine()
        e.add_rule(AlertRuleConfig(id="r1", name="Old"))
        assert e.update_rule("r1", name="New") is True
        assert e.get_rule("r1").name == "New"

    def test_update_nonexistent(self):
        e = RulesEngine()
        assert e.update_rule("nope", name="X") is False

    def test_clear(self):
        e = RulesEngine()
        e.add_rule(AlertRuleConfig(id="r1", name="A"))
        e.add_rule(AlertRuleConfig(id="r2", name="B"))
        count = e.clear()
        assert count == 2
        assert len(e.rules) == 0
