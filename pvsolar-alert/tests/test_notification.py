"""Testes do notification_manager do pvSolar Alert."""

import pytest
from src.core.config import AlertSeverity, AlertStatus, NotificationChannel
from src.core.notification_manager import (
    Alert,
    NotificationManager,
    NotificationResult,
)

# ---------------------------------------------------------------------------
# Alert
# ---------------------------------------------------------------------------

class TestAlert:
    def test_create_alert(self):
        a = Alert(source="inverter_1", title="Overheat", message="Temp > 80C")
        assert a.source == "inverter_1"
        assert a.severity == AlertSeverity.MEDIUM
        assert a.status == AlertStatus.PENDING

    def test_acknowledge(self):
        a = Alert(source="s1", title="t", message="m")
        a.acknowledge()
        assert a.status == AlertStatus.ACKNOWLEDGED
        assert a.acknowledged_at is not None

    def test_resolve(self):
        a = Alert(source="s1", title="t", message="m")
        a.resolve()
        assert a.status == AlertStatus.RESOLVED
        assert a.resolved_at is not None

    def test_escalate(self):
        a = Alert(source="s1", title="t", message="m")
        a.escalate()
        assert a.status == AlertStatus.ESCALATED

    def test_to_dict(self):
        a = Alert(source="s1", title="t", message="m")
        d = a.to_dict()
        assert d["source"] == "s1"
        assert d["title"] == "t"
        assert "id" in d
        assert "created_at" in d


# ---------------------------------------------------------------------------
# NotificationResult
# ---------------------------------------------------------------------------

class TestNotificationResult:
    def test_create_result(self):
        r = NotificationResult(channel=NotificationChannel.EMAIL, success=True)
        assert r.channel == NotificationChannel.EMAIL
        assert r.success is True

    def test_create_failure(self):
        r = NotificationResult(
            channel=NotificationChannel.SMS, success=False, message="Error"
        )
        assert r.success is False
        assert r.message == "Error"


# ---------------------------------------------------------------------------
# NotificationManager
# ---------------------------------------------------------------------------

class TestNotificationManager:
    def test_create_manager(self):
        m = NotificationManager()
        assert len(m.alerts) == 0

    def test_create_alert(self):
        m = NotificationManager()
        a = m.create_alert(source="inv1", title="t", message="m")
        assert a.source == "inv1"
        assert len(m.alerts) == 1

    def test_get_alert(self):
        m = NotificationManager()
        a = m.create_alert(source="s", title="t", message="m")
        found = m.get_alert(a.id)
        assert found is not None
        assert found.id == a.id

    def test_get_nonexistent_alert(self):
        m = NotificationManager()
        assert m.get_alert("nonexistent") is None

    def test_get_active_alerts(self):
        m = NotificationManager()
        m.create_alert(source="s", title="t1", message="m1")
        m.create_alert(source="s", title="t2", message="m2")
        assert len(m.get_active_alerts()) == 2

    def test_get_alerts_by_severity(self):
        m = NotificationManager()
        m.create_alert(source="s", title="t", message="m", severity=AlertSeverity.CRITICAL)
        m.create_alert(source="s", title="t", message="m", severity=AlertSeverity.LOW)
        critical = m.get_alerts_by_severity(AlertSeverity.CRITICAL)
        assert len(critical) == 1

    def test_get_alerts_by_source(self):
        m = NotificationManager()
        m.create_alert(source="inv1", title="t", message="m")
        m.create_alert(source="inv2", title="t", message="m")
        assert len(m.get_alerts_by_source("inv1")) == 1

    def test_acknowledge_alert(self):
        m = NotificationManager()
        a = m.create_alert(source="s", title="t", message="m")
        assert m.acknowledge_alert(a.id) is True
        assert a.status == AlertStatus.ACKNOWLEDGED

    def test_acknowledge_nonexistent(self):
        m = NotificationManager()
        assert m.acknowledge_alert("nope") is False

    def test_resolve_alert(self):
        m = NotificationManager()
        a = m.create_alert(source="s", title="t", message="m")
        assert m.resolve_alert(a.id) is True
        assert a.status == AlertStatus.RESOLVED

    def test_acknowledge_all(self):
        m = NotificationManager()
        m.create_alert(source="s", title="t1", message="m1")
        m.create_alert(source="s", title="t2", message="m2")
        count = m.acknowledge_all()
        assert count == 2
        assert len(m.get_active_alerts()) == 0

    def test_get_statistics(self):
        m = NotificationManager()
        m.create_alert(source="s", title="t", message="m", severity=AlertSeverity.HIGH)
        m.create_alert(source="s", title="t", message="m", severity=AlertSeverity.LOW)
        stats = m.get_statistics()
        assert stats["total"] == 2
        assert stats["active"] == 2

    def test_send_notification(self):
        m = NotificationManager()
        a = m.create_alert(source="s", title="t", message="m")
        import asyncio
        result = asyncio.run(
            m.send_notification(a, NotificationChannel.EMAIL, {}, 50, 200)
        )
        assert result.success is True
        assert "email" in a.channels_sent

    def test_send_multi_channel(self):
        m = NotificationManager()
        a = m.create_alert(source="s", title="t", message="m")
        import asyncio
        results = asyncio.run(
            m.send_multi_channel(
                a,
                [NotificationChannel.EMAIL, NotificationChannel.SMS],
                {},
                50,
                200,
            )
        )
        assert len(results) == 2
        assert len(a.channels_sent) == 2

    def test_notification_history(self):
        m = NotificationManager()
        a = m.create_alert(source="s", title="t", message="m")
        import asyncio
        asyncio.run(
            m.send_notification(a, NotificationChannel.EMAIL, {}, 50, 200)
        )
        history = m.get_notification_history(a.id)
        assert len(history) == 1

    def test_clear_resolved(self):
        m = NotificationManager()
        a1 = m.create_alert(source="s", title="t1", message="m1")
        m.create_alert(source="s", title="t2", message="m2")
        m.resolve_alert(a1.id)
        count = m.clear_resolved()
        assert count == 1
        assert len(m.alerts) == 1
