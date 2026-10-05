"""Testes do escalation_engine do pvSolar Alert."""

import pytest
from src.core.config import (
    AlertSeverity,
    EscalationContact,
    EscalationLevel,
    EscalationRuleConfig,
    NotificationChannel,
)
from src.core.notification_manager import Alert
from src.escalation.escalation_engine import (
    EscalationManager,
    get_escalation_level_for_severity,
    get_next_level,
)


class TestHelpers:
    def test_severity_to_level_critical(self):
        assert get_escalation_level_for_severity(AlertSeverity.CRITICAL) == EscalationLevel.LEVEL_4

    def test_severity_to_level_high(self):
        assert get_escalation_level_for_severity(AlertSeverity.HIGH) == EscalationLevel.LEVEL_3

    def test_severity_to_level_medium(self):
        assert get_escalation_level_for_severity(AlertSeverity.MEDIUM) == EscalationLevel.LEVEL_2

    def test_severity_to_level_low(self):
        assert get_escalation_level_for_severity(AlertSeverity.LOW) == EscalationLevel.LEVEL_1

    def test_next_level(self):
        assert get_next_level(EscalationLevel.LEVEL_1) == EscalationLevel.LEVEL_2
        assert get_next_level(EscalationLevel.LEVEL_2) == EscalationLevel.LEVEL_3
        assert get_next_level(EscalationLevel.LEVEL_3) == EscalationLevel.LEVEL_4
        assert get_next_level(EscalationLevel.LEVEL_4) is None


class TestEscalationManager:
    def test_create_manager(self):
        m = EscalationManager()
        assert len(m.escalation_rules) == 0

    def test_init_escalation(self):
        m = EscalationManager()
        alert = Alert(source="s", title="t", message="m", severity=AlertSeverity.HIGH)
        m.init_escalation(alert)
        level = m.get_current_level(alert.id)
        assert level == EscalationLevel.LEVEL_3

    def test_get_current_level_default(self):
        m = EscalationManager()
        assert m.get_current_level("nonexistent") == EscalationLevel.LEVEL_1

    def test_should_escalate(self):
        m = EscalationManager()
        alert = Alert(source="s", title="t", message="m", severity=AlertSeverity.MEDIUM)
        m.init_escalation(alert)
        assert m.should_escalate(alert.id) is True

    def test_should_not_escalate_max_level(self):
        m = EscalationManager()
        alert = Alert(source="s", title="t", message="m", severity=AlertSeverity.CRITICAL)
        m.init_escalation(alert)
        assert m.should_escalate(alert.id) is False

    def test_escalate(self):
        m = EscalationManager()
        alert = Alert(source="s", title="t", message="m", severity=AlertSeverity.MEDIUM)
        m.init_escalation(alert)
        next_level = m.escalate(alert.id)
        assert next_level == EscalationLevel.LEVEL_3

    def test_escalate_max(self):
        m = EscalationManager()
        alert = Alert(source="s", title="t", message="m", severity=AlertSeverity.CRITICAL)
        m.init_escalation(alert)
        result = m.escalate(alert.id)
        assert result is None

    def test_get_rule_for_level(self):
        m = EscalationManager()
        rule = EscalationRuleConfig(level=EscalationLevel.LEVEL_2, wait_seconds=120)
        m.escalation_rules.append(rule)
        found = m.get_rule_for_level(EscalationLevel.LEVEL_2)
        assert found is not None
        assert found.wait_seconds == 120

    def test_get_rule_none(self):
        m = EscalationManager()
        assert m.get_rule_for_level(EscalationLevel.LEVEL_1) is None

    def test_get_escalation_contacts(self):
        m = EscalationManager()
        contact = EscalationContact(
            name="Admin",
            email="admin@test.com",
            channels=[NotificationChannel.EMAIL],
        )
        rule = EscalationRuleConfig(
            level=EscalationLevel.LEVEL_2, contacts=[contact]
        )
        m.escalation_rules.append(rule)
        contacts = m.get_escalation_contacts(EscalationLevel.LEVEL_2)
        assert len(contacts) == 1
        assert contacts[0]["name"] == "Admin"

    def test_get_escalation_channels(self):
        m = EscalationManager()
        contact = EscalationContact(
            name="A",
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        )
        rule = EscalationRuleConfig(
            level=EscalationLevel.LEVEL_1, contacts=[contact]
        )
        m.escalation_rules.append(rule)
        channels = m.get_escalation_channels(EscalationLevel.LEVEL_1)
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.SMS in channels

    def test_get_escalation_wait_seconds(self):
        m = EscalationManager()
        rule = EscalationRuleConfig(
            level=EscalationLevel.LEVEL_1, wait_seconds=600
        )
        m.escalation_rules.append(rule)
        assert m.get_escalation_wait_seconds(EscalationLevel.LEVEL_1) == 600

    def test_get_escalation_stats(self):
        m = EscalationManager()
        alert1 = Alert(source="s", title="t", message="m", severity=AlertSeverity.LOW)
        alert2 = Alert(source="s", title="t", message="m", severity=AlertSeverity.HIGH)
        m.init_escalation(alert1)
        m.init_escalation(alert2)
        stats = m.get_escalation_stats()
        assert stats["total_escalated"] == 2

    def test_reset_escalation(self):
        m = EscalationManager()
        alert = Alert(source="s", title="t", message="m")
        m.init_escalation(alert)
        assert m.reset_escalation(alert.id) is True
        assert m.get_current_level(alert.id) == EscalationLevel.LEVEL_1

    def test_clear_all(self):
        m = EscalationManager()
        alert = Alert(source="s", title="t", message="m")
        m.init_escalation(alert)
        count = m.clear_all()
        assert count == 1
        assert len(m.alert_escalation_state) == 0
