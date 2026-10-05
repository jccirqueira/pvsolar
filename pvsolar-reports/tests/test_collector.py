"""
Tests for pvSolar Reports Data Collector.
"""

import pytest
from datetime import datetime, timezone
from src.collectors.data_collector import (
    AlarmData,
    DataCollector,
    MaintenanceData,
    PerformanceData,
    TelemetryData,
)
from src.core.config import AnalyticsConfig, GatewayConfig


class TestTelemetryData:
    def test_create_telemetry(self):
        data = TelemetryData()
        assert isinstance(data.timestamp, datetime)
        assert data.power_kw == 0.0
        assert data.energy_kwh == 0.0
        assert data.inverters == []

    def test_to_dict(self):
        data = TelemetryData()
        data.power_kw = 50.0
        data.energy_kwh = 400.0
        d = data.to_dict()
        assert d["power_kw"] == 50.0
        assert d["energy_kwh"] == 400.0
        assert "timestamp" in d


class TestAlarmData:
    def test_create_alarm(self):
        now = datetime.now(timezone.utc)
        alarm = AlarmData("alarm_1", "critical", "Test alarm", "inverter_1", now)
        assert alarm.alarm_id == "alarm_1"
        assert alarm.level == "critical"
        assert alarm.message == "Test alarm"
        assert alarm.source == "inverter_1"
        assert alarm.acknowledged is False

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        alarm = AlarmData("alarm_1", "warning", "High temp", "inv_1", now)
        d = alarm.to_dict()
        assert d["alarm_id"] == "alarm_1"
        assert d["level"] == "warning"
        assert d["acknowledged"] is False


class TestPerformanceData:
    def test_create_performance(self):
        perf = PerformanceData()
        assert perf.overall_score == 0.0
        assert perf.grade == "--"
        assert perf.recommendations == []

    def test_to_dict(self):
        perf = PerformanceData()
        perf.overall_score = 85.0
        perf.grade = "A"
        perf.pr = 82.5
        d = perf.to_dict()
        assert d["overall_score"] == 85.0
        assert d["grade"] == "A"
        assert d["pr"] == 82.5


class TestMaintenanceData:
    def test_create_maintenance(self):
        maint = MaintenanceData()
        assert maint.predictions == []
        assert maint.risk_level == "low"
        assert maint.urgent_actions == []

    def test_to_dict(self):
        maint = MaintenanceData()
        maint.risk_level = "medium"
        maint.urgent_actions = ["Clean panels"]
        d = maint.to_dict()
        assert d["risk_level"] == "medium"
        assert "Clean panels" in d["urgent_actions"]


class TestDataCollector:
    def setup_method(self):
        self.gateway = GatewayConfig(url="http://localhost:8000")
        self.analytics = AnalyticsConfig(url="http://localhost:8001")

    def test_create_collector(self):
        collector = DataCollector(self.gateway, self.analytics)
        assert collector.gateway.url == "http://localhost:8000"
        assert collector.analytics.url == "http://localhost:8001"
        assert collector._session is None

    def test_headers_with_api_key(self):
        config = GatewayConfig(url="http://localhost:8000", api_key="test_key")
        collector = DataCollector(config, self.analytics)
        headers = collector._headers(config)
        assert headers["Authorization"] == "Bearer test_key"
        assert headers["Content-Type"] == "application/json"

    def test_headers_without_api_key(self):
        collector = DataCollector(self.gateway, self.analytics)
        headers = collector._headers(self.gateway)
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"
