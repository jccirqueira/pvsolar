"""Testes do módulo config do pvSolar Alert."""

from pathlib import Path

import pytest
from src.core.config import (
    AlertConfig,
    AlertRuleConfig,
    AlertSeverity,
    AlertStatus,
    ChannelConfig,
    DatabaseConfig,
    EscalationContact,
    EscalationLevel,
    EscalationRuleConfig,
    NotificationChannel,
    NotificationConfig,
    RecipientConfig,
    RuleCondition,
    TimeWindow,
    load_config,
)

# ---------------------------------------------------------------------------
# NotificationChannel
# ---------------------------------------------------------------------------

class TestNotificationChannel:
    def test_email(self):
        assert NotificationChannel.EMAIL == "email"

    def test_sms(self):
        assert NotificationChannel.SMS == "sms"

    def test_telegram(self):
        assert NotificationChannel.TELEGRAM == "telegram"

    def test_whatsapp(self):
        assert NotificationChannel.WHATSAPP == "whatsapp"

    def test_webhook(self):
        assert NotificationChannel.WEBHOOK == "webhook"


# ---------------------------------------------------------------------------
# AlertSeverity
# ---------------------------------------------------------------------------

class TestAlertSeverity:
    def test_critical(self):
        assert AlertSeverity.CRITICAL == "critical"

    def test_high(self):
        assert AlertSeverity.HIGH == "high"

    def test_medium(self):
        assert AlertSeverity.MEDIUM == "medium"

    def test_low(self):
        assert AlertSeverity.LOW == "low"

    def test_info(self):
        assert AlertSeverity.INFO == "info"


# ---------------------------------------------------------------------------
# AlertStatus
# ---------------------------------------------------------------------------

class TestAlertStatus:
    def test_pending(self):
        assert AlertStatus.PENDING == "pending"

    def test_sent(self):
        assert AlertStatus.SENT == "sent"

    def test_acknowledged(self):
        assert AlertStatus.ACKNOWLEDGED == "acknowledged"

    def test_resolved(self):
        assert AlertStatus.RESOLVED == "resolved"

    def test_escalated(self):
        assert AlertStatus.ESCALATED == "escalated"


# ---------------------------------------------------------------------------
# EscalationLevel
# ---------------------------------------------------------------------------

class TestEscalationLevel:
    def test_level_1(self):
        assert EscalationLevel.LEVEL_1 == "level_1"

    def test_level_2(self):
        assert EscalationLevel.LEVEL_2 == "level_2"

    def test_level_3(self):
        assert EscalationLevel.LEVEL_3 == "level_3"

    def test_level_4(self):
        assert EscalationLevel.LEVEL_4 == "level_4"


# ---------------------------------------------------------------------------
# TimeWindow
# ---------------------------------------------------------------------------

class TestTimeWindow:
    def test_business_hours(self):
        assert TimeWindow.BUSINESS_HOURS == "business_hours"

    def test_always(self):
        assert TimeWindow.ALWAYS == "always"


# ---------------------------------------------------------------------------
# ChannelConfig
# ---------------------------------------------------------------------------

class TestChannelConfig:
    def test_defaults(self):
        c = ChannelConfig()
        assert c.enabled is False
        assert c.api_key is None
        assert c.timeout == 30

    def test_with_values(self):
        c = ChannelConfig(enabled=True, api_key="key123", timeout=60)
        assert c.enabled is True
        assert c.api_key == "key123"
        assert c.timeout == 60


# ---------------------------------------------------------------------------
# RecipientConfig
# ---------------------------------------------------------------------------

class TestRecipientConfig:
    def test_defaults(self):
        r = RecipientConfig(name="Test User")
        assert r.name == "Test User"
        assert r.email is None
        assert r.channels == []
        assert r.time_window == TimeWindow.ALWAYS

    def test_with_values(self):
        r = RecipientConfig(
            name="Admin",
            email="admin@test.com",
            phone="+5511999999999",
            channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
        )
        assert r.email == "admin@test.com"
        assert r.phone == "+5511999999999"
        assert len(r.channels) == 2


# ---------------------------------------------------------------------------
# EscalationRuleConfig
# ---------------------------------------------------------------------------

class TestEscalationRuleConfig:
    def test_defaults(self):
        e = EscalationRuleConfig()
        assert e.level == EscalationLevel.LEVEL_1
        assert e.wait_seconds == 300
        assert e.contacts == []


# ---------------------------------------------------------------------------
# NotificationConfig
# ---------------------------------------------------------------------------

class TestNotificationConfig:
    def test_defaults(self):
        n = NotificationConfig()
        assert n.max_per_hour == 50
        assert n.max_per_day == 200
        assert n.retry_attempts == 3


# ---------------------------------------------------------------------------
# AlertRuleConfig
# ---------------------------------------------------------------------------

class TestAlertRuleConfig:
    def test_defaults(self):
        r = AlertRuleConfig(id="rule_1", name="Test Rule")
        assert r.id == "rule_1"
        assert r.enabled is True
        assert r.severity == AlertSeverity.MEDIUM

    def test_with_conditions(self):
        r = AlertRuleConfig(
            id="r1",
            name="High Temp",
            conditions=[
                RuleCondition(field="temperature", operator="gt", value=50.0)
            ],
        )
        assert len(r.conditions) == 1
        assert r.conditions[0].operator == "gt"


# ---------------------------------------------------------------------------
# DatabaseConfig
# ---------------------------------------------------------------------------

class TestDatabaseConfig:
    def test_defaults(self):
        d = DatabaseConfig()
        assert d.path == "data/alerts.db"


# ---------------------------------------------------------------------------
# AlertConfig
# ---------------------------------------------------------------------------

class TestAlertConfig:
    def test_defaults(self):
        c = AlertConfig()
        assert c.company_name == "pvSolar Alert"
        assert c.debug is False
        assert c.api.port == 8004

    def test_with_sites(self):
        c = AlertConfig(
            recipients=[
                RecipientConfig(name="User1", email="u1@test.com"),
                RecipientConfig(name="User2", email="u2@test.com"),
            ]
        )
        assert len(c.recipients) == 2


# ---------------------------------------------------------------------------
# Load Config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_default(self):
        c = load_config()
        assert c.company_name == "pvSolar Alert"

    def test_load_nonexistent(self):
        c = load_config("/nonexistent/path.yaml")
        assert c.company_name == "pvSolar Alert"

    def test_load_yaml(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text(
            "company_name: TestCo\ndebug: true\napi:\n  port: 9000\n"
        )
        c = load_config(config_file)
        assert c.company_name == "TestCo"
        assert c.debug is True
        assert c.api.port == 9000
