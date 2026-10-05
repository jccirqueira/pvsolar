"""
Tests for pvSolar Fleet Alert Aggregator.
"""

import pytest
from src.alerts.alert_aggregator import AlertAggregator, FleetAlert
from src.core.config import AlertSeverity, AlertStatus


class TestFleetAlert:
    def test_create_alert(self):
        alert = FleetAlert(
            alert_id="a1",
            site_id="site_1",
            site_name="Test Site",
            severity=AlertSeverity.CRITICAL,
            message="Inverter offline",
            source="inverter_1",
        )
        assert alert.alert_id == "a1"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.ACTIVE

    def test_acknowledge(self):
        alert = FleetAlert("a1", "s1", "S1", AlertSeverity.WARNING, "msg")
        alert.acknowledge("operator")
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "operator"
        assert alert.acknowledged_at is not None

    def test_resolve(self):
        alert = FleetAlert("a1", "s1", "S1", AlertSeverity.INFO, "msg")
        alert.resolve()
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_at is not None

    def test_escalate(self):
        alert = FleetAlert("a1", "s1", "S1", AlertSeverity.CRITICAL, "msg")
        assert alert.escalation_level == 0
        alert.escalate()
        assert alert.escalation_level == 1
        alert.escalate()
        assert alert.escalation_level == 2

    def test_to_dict(self):
        alert = FleetAlert("a1", "s1", "S1", AlertSeverity.WARNING, "High temp")
        d = alert.to_dict()
        assert d["alert_id"] == "a1"
        assert d["severity"] == "warning"
        assert d["status"] == "active"


class TestAlertAggregator:
    def test_create_aggregator(self):
        agg = AlertAggregator()
        stats = agg.get_statistics()
        assert stats["total_alerts"] == 0

    def test_add_alert(self):
        agg = AlertAggregator()
        alert = FleetAlert("a1", "s1", "S1", AlertSeverity.CRITICAL, "msg")
        agg.add_alert(alert)
        assert len(agg.get_active_alerts()) == 1

    def test_create_alert(self):
        agg = AlertAggregator()
        alert = agg.create_alert("s1", "S1", AlertSeverity.WARNING, "High temp")
        assert alert.site_id == "s1"
        assert alert.severity == AlertSeverity.WARNING
        assert len(agg.get_active_alerts()) == 1

    def test_acknowledge_alert(self):
        agg = AlertAggregator()
        alert = agg.create_alert("s1", "S1", AlertSeverity.CRITICAL, "msg")
        result = agg.acknowledge_alert(alert.alert_id, "operator")
        assert result is True
        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_acknowledge_nonexistent(self):
        agg = AlertAggregator()
        result = agg.acknowledge_alert("nonexistent")
        assert result is False

    def test_resolve_alert(self):
        agg = AlertAggregator()
        alert = agg.create_alert("s1", "S1", AlertSeverity.WARNING, "msg")
        result = agg.resolve_alert(alert.alert_id)
        assert result is True
        assert alert.status == AlertStatus.RESOLVED

    def test_acknowledge_all(self):
        agg = AlertAggregator()
        agg.create_alert("s1", "S1", AlertSeverity.CRITICAL, "msg1")
        agg.create_alert("s1", "S1", AlertSeverity.WARNING, "msg2")
        count = agg.acknowledge_all("admin")
        assert count == 2
        assert len(agg.get_active_alerts()) == 0

    def test_get_alerts_by_severity(self):
        agg = AlertAggregator()
        agg.create_alert("s1", "S1", AlertSeverity.CRITICAL, "msg1")
        agg.create_alert("s1", "S1", AlertSeverity.WARNING, "msg2")
        agg.create_alert("s1", "S1", AlertSeverity.INFO, "msg3")
        critical = agg.get_alerts(severity=AlertSeverity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].severity == AlertSeverity.CRITICAL

    def test_get_alerts_by_site(self):
        agg = AlertAggregator()
        agg.create_alert("s1", "S1", AlertSeverity.CRITICAL, "msg1")
        agg.create_alert("s2", "S2", AlertSeverity.WARNING, "msg2")
        s1_alerts = agg.get_alerts(site_id="s1")
        assert len(s1_alerts) == 1

    def test_get_statistics(self):
        agg = AlertAggregator()
        agg.create_alert("s1", "S1", AlertSeverity.CRITICAL, "msg1")
        agg.create_alert("s1", "S1", AlertSeverity.WARNING, "msg2")
        stats = agg.get_statistics()
        assert stats["total_alerts"] == 2
        assert stats["active"] == 2
        assert stats["critical"] == 1
        assert stats["warning"] == 1

    def test_get_site_statistics(self):
        agg = AlertAggregator()
        agg.create_alert("s1", "S1", AlertSeverity.CRITICAL, "msg1")
        agg.create_alert("s1", "S1", AlertSeverity.WARNING, "msg2")
        agg.create_alert("s2", "S2", AlertSeverity.INFO, "msg3")
        stats = agg.get_site_statistics("s1")
        assert stats["total"] == 2
        assert stats["active"] == 2

    def test_callback(self):
        agg = AlertAggregator()
        received = []
        agg.register_callback(lambda a: received.append(a))
        agg.create_alert("s1", "S1", AlertSeverity.INFO, "msg")
        assert len(received) == 1

    def test_max_alerts(self):
        agg = AlertAggregator(max_alerts=5)
        for i in range(10):
            agg.create_alert("s1", "S1", AlertSeverity.INFO, f"msg{i}")
        assert len(agg.get_alerts()) == 5
