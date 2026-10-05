"""
Tests for pvSolar Fleet Configuration.
"""

import pytest
from src.core.config import (
    AlertAggregatorConfig,
    AlertSeverity,
    AlertStatus,
    APIConfig,
    AnalyticsServiceConfig,
    ComparisonConfig,
    ComparisonMetric,
    FleetConfig,
    GatewayServiceConfig,
    SiteConfig,
    SiteStatus,
    load_config,
)


class TestSiteConfig:
    def test_create_site(self):
        config = SiteConfig(
            id="site_1",
            name="Test Site",
            gateway_url="http://localhost:8000",
            analytics_url="http://localhost:8001",
            capacity_kw=100.0,
            num_inverters=6,
            latitude=-23.55,
            longitude=-46.63,
        )
        assert config.id == "site_1"
        assert config.name == "Test Site"
        assert config.capacity_kw == 100.0
        assert config.num_inverters == 6
        assert config.region == "default"

    def test_site_defaults(self):
        config = SiteConfig(
            id="s1",
            name="S1",
            gateway_url="http://localhost:8000",
            analytics_url="http://localhost:8001",
            capacity_kw=50.0,
            num_inverters=3,
            latitude=0.0,
            longitude=0.0,
        )
        assert config.timezone == "America/Sao_Paulo"
        assert config.api_key is None


class TestGatewayServiceConfig:
    def test_defaults(self):
        config = GatewayServiceConfig()
        assert config.url == "http://localhost:8000"
        assert config.timeout == 30


class TestAnalyticsServiceConfig:
    def test_defaults(self):
        config = AnalyticsServiceConfig()
        assert config.url == "http://localhost:8001"
        assert config.timeout == 30


class TestAlertAggregatorConfig:
    def test_defaults(self):
        config = AlertAggregatorConfig()
        assert config.enabled is True
        assert config.max_alerts_per_site == 100
        assert config.escalation_timeout == 300


class TestComparisonConfig:
    def test_defaults(self):
        config = ComparisonConfig()
        assert config.enabled is True
        assert config.default_metric == ComparisonMetric.PR
        assert config.ranking_window == 30


class TestAPIConfig:
    def test_defaults(self):
        config = APIConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8003


class TestFleetConfig:
    def test_defaults(self):
        config = FleetConfig()
        assert isinstance(config.gateway, GatewayServiceConfig)
        assert isinstance(config.analytics, AnalyticsServiceConfig)
        assert isinstance(config.alerts, AlertAggregatorConfig)
        assert isinstance(config.comparison, ComparisonConfig)
        assert isinstance(config.api, APIConfig)
        assert config.sites == []
        assert config.debug is False

    def test_with_sites(self):
        site = SiteConfig(
            id="s1", name="S1",
            gateway_url="http://localhost:8000",
            analytics_url="http://localhost:8001",
            capacity_kw=100.0, num_inverters=6,
            latitude=0.0, longitude=0.0,
        )
        config = FleetConfig(sites=[site])
        assert len(config.sites) == 1
        assert config.sites[0].id == "s1"


class TestEnums:
    def test_site_status(self):
        assert SiteStatus.ONLINE == "online"
        assert SiteStatus.OFFLINE == "offline"
        assert SiteStatus.MAINTENANCE == "maintenance"
        assert SiteStatus.DEGRADED == "degraded"

    def test_alert_severity(self):
        assert AlertSeverity.CRITICAL == "critical"
        assert AlertSeverity.WARNING == "warning"
        assert AlertSeverity.INFO == "info"

    def test_alert_status(self):
        assert AlertStatus.ACTIVE == "active"
        assert AlertStatus.ACKNOWLEDGED == "acknowledged"
        assert AlertStatus.RESOLVED == "resolved"

    def test_comparison_metric(self):
        assert ComparisonMetric.ENERGY == "energy"
        assert ComparisonMetric.PR == "pr"
        assert ComparisonMetric.SCORE == "score"


class TestLoadConfig:
    def test_load_default(self):
        config = load_config()
        assert isinstance(config, FleetConfig)

    def test_load_nonexistent(self):
        config = load_config("nonexistent.yaml")
        assert isinstance(config, FleetConfig)

    def test_load_via_env_pvsolar_config(self, tmp_path, monkeypatch):
        cfg = tmp_path / "custom.yaml"
        cfg.write_text('company_name: "FROTA_VIA_ENV"\n', encoding="utf-8")
        monkeypatch.setenv("PVSOLAR_CONFIG", str(cfg))
        config = load_config()
        assert config.company_name == "FROTA_VIA_ENV"
