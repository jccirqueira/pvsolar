import pytest
from src.core.config import CollectorConfig, ServiceType
from src.collectors.collectors import (
    BaseCollector, GatewayCollector, AnalyticsCollector, ScadaCollector,
    ReportsCollector, FleetCollector, AlertCollector, GridCollector,
    TwinCollector, AuthCollector, BackupCollector, SchedulerCollector,
    create_collector, COLLECTOR_MAP,
)


class TestBaseCollector:
    def test_create(self):
        c = BaseCollector(ServiceType.GATEWAY, CollectorConfig())
        assert c.service_type == ServiceType.GATEWAY

    def test_create_all_collectors(self):
        for st in ServiceType:
            if st == ServiceType.WEB:
                continue
            config = CollectorConfig(url=f"http://localhost:8000")
            c = create_collector(st, config)
            assert c.service_type == st

    def test_unknown_service_raises(self):
        with pytest.raises(ValueError):
            create_collector("unknown", CollectorConfig())

    def test_collector_map_has_all_services(self):
        for st in ServiceType:
            if st == ServiceType.WEB:
                continue
            assert st in COLLECTOR_MAP


class TestCollectors:
    def test_gateway_collector(self):
        c = GatewayCollector(CollectorConfig())
        assert c.service_type == ServiceType.GATEWAY

    def test_analytics_collector(self):
        c = AnalyticsCollector(CollectorConfig())
        assert c.service_type == ServiceType.ANALYTICS

    def test_scada_collector(self):
        c = ScadaCollector(CollectorConfig())
        assert c.service_type == ServiceType.SCADA

    def test_reports_collector(self):
        c = ReportsCollector(CollectorConfig())
        assert c.service_type == ServiceType.REPORTS

    def test_fleet_collector(self):
        c = FleetCollector(CollectorConfig())
        assert c.service_type == ServiceType.FLEET

    def test_alert_collector(self):
        c = AlertCollector(CollectorConfig())
        assert c.service_type == ServiceType.ALERT

    def test_grid_collector(self):
        c = GridCollector(CollectorConfig())
        assert c.service_type == ServiceType.GRID

    def test_twin_collector(self):
        c = TwinCollector(CollectorConfig())
        assert c.service_type == ServiceType.TWIN

    def test_auth_collector(self):
        c = AuthCollector(CollectorConfig())
        assert c.service_type == ServiceType.AUTH

    def test_backup_collector(self):
        c = BackupCollector(CollectorConfig())
        assert c.service_type == ServiceType.BACKUP

    def test_scheduler_collector(self):
        c = SchedulerCollector(CollectorConfig())
        assert c.service_type == ServiceType.SCHEDULER
