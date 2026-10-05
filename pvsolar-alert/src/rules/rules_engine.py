"""Engine de regras de alerta."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from src.core.config import (
    AlertRuleConfig,
    AlertSeverity,
    RuleCondition,
)

logger = structlog.get_logger()


@dataclass
class RuleMatch:
    """Resultado de uma match de regra."""

    rule_id: str
    rule_name: str
    severity: AlertSeverity
    matched_conditions: list[str] = field(default_factory=list)


class RulesEngine:
    """Engine de avaliação de regras."""

    def __init__(self) -> None:
        self.rules: list[AlertRuleConfig] = []

    def add_rule(self, rule: AlertRuleConfig) -> None:
        """Adiciona uma regra."""
        self.rules.append(rule)
        logger.info("rule.added", rule_id=rule.id, name=rule.name)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove uma regra."""
        for i, r in enumerate(self.rules):
            if r.id == rule_id:
                del self.rules[i]
                logger.info("rule.removed", rule_id=rule_id)
                return True
        return False

    def get_rule(self, rule_id: str) -> AlertRuleConfig | None:
        """Busca regra por ID."""
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None

    def get_active_rules(self) -> list[AlertRuleConfig]:
        """Retorna regras ativas."""
        return [r for r in self.rules if r.enabled]

    def evaluate_condition(
        self, condition: RuleCondition, data: dict
    ) -> bool:
        """Avalia uma condição."""
        field_value = data.get(condition.field)
        if field_value is None:
            return False

        try:
            value = float(field_value)
        except (ValueError, TypeError):
            return str(field_value).lower() == str(condition.value).lower()

        op = condition.operator
        target = condition.value

        if op == "eq":
            return value == target
        elif op == "ne":
            return value != target
        elif op == "gt":
            return value > target
        elif op == "gte":
            return value >= target
        elif op == "lt":
            return value < target
        elif op == "lte":
            return value <= target
        return False

    def evaluate_rule(
        self, rule: AlertRuleConfig, data: dict
    ) -> bool:
        """Avalia se uma regra corresponde aos dados."""
        if not rule.enabled:
            return False

        if not rule.conditions:
            return True

        for condition in rule.conditions:
            if not self.evaluate_condition(condition, data):
                return False

        return True

    def evaluate_all(self, data: dict) -> list[RuleMatch]:
        """Avalia todas as regras ativas."""
        matches = []
        for rule in self.get_active_rules():
            if self.evaluate_rule(rule, data):
                matched_conditions = []
                for c in rule.conditions:
                    field_value = data.get(c.field)
                    matched_conditions.append(
                        f"{c.field} {c.operator} {c.value} (actual: {field_value})"
                    )
                matches.append(
                    RuleMatch(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        severity=rule.severity,
                        matched_conditions=matched_conditions,
                    )
                )
                logger.info(
                    "rule.matched",
                    rule_id=rule.id,
                    severity=rule.severity.value,
                )
        return matches

    def get_rules_by_severity(
        self, severity: AlertSeverity
    ) -> list[AlertRuleConfig]:
        """Retorna regras por severidade."""
        return [r for r in self.rules if r.severity == severity]

    def get_rules_count(self) -> dict:
        """Retorna contagem de regras."""
        active = len(self.get_active_rules())
        total = len(self.rules)
        by_severity = {}
        for s in AlertSeverity:
            by_severity[s.value] = len(self.get_rules_by_severity(s))
        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "by_severity": by_severity,
        }

    def update_rule(
        self,
        rule_id: str,
        name: str | None = None,
        enabled: bool | None = None,
        conditions: list[RuleCondition] | None = None,
        severity: AlertSeverity | None = None,
    ) -> bool:
        """Atualiza uma regra."""
        rule = self.get_rule(rule_id)
        if rule is None:
            return False

        if name is not None:
            rule.name = name
        if enabled is not None:
            rule.enabled = enabled
        if conditions is not None:
            rule.conditions = conditions
        if severity is not None:
            rule.severity = severity

        logger.info("rule.updated", rule_id=rule_id)
        return True

    def clear(self) -> int:
        """Limpa todas as regras."""
        count = len(self.rules)
        self.rules.clear()
        return count
