import pytest
from src.core.config import (
    APIConfig,
    CollectorConfig,
    ExporterConfig,
    MetricType,
    ServiceType,
    load_config,
)


class TestEnums:
    def test_metric_type(self):
        assert MetricType.COUNTER == "counter"
        assert MetricType.GAUGE == "gauge"
        assert MetricType.HISTOGRAM == "histogram"
        assert MetricType.SUMMARY == "summary"

    def test_service_type(self):
        assert ServiceType.GATEWAY == "gateway"
        assert ServiceType.ANALYTICS == "analytics"
        assert ServiceType.SCADA == "scada"
        assert ServiceType.REPORTS == "reports"
        assert ServiceType.FLEET == "fleet"
        assert ServiceType.ALERT == "alert"
        assert ServiceType.GRID == "grid"
        assert ServiceType.TWIN == "twin"
        assert ServiceType.AUTH == "auth"
        assert ServiceType.WEB == "web"
        assert ServiceType.BACKUP == "backup"
        assert ServiceType.SCHEDULER == "scheduler"


class TestCollectorConfig:
    def test_defaults(self):
        c = CollectorConfig()
        assert c.enabled is True
        assert c.url == ""
        assert c.port == 0
        assert c.interval_seconds == 15
        assert c.timeout_seconds == 10
        assert c.labels == {}

    def test_custom(self):
        c = CollectorConfig(url="http://localhost:8000", port=8000, interval_seconds=30)
        assert c.url == "http://localhost:8000"
        assert c.interval_seconds == 30


class TestAPIConfig:
    def test_defaults(self):
        c = APIConfig()
        assert c.host == "0.0.0.0"
        assert c.port == 8010

    def test_custom(self):
        c = APIConfig(port=9000)
        assert c.port == 9000


class TestExporterConfig:
    def test_defaults(self):
        c = ExporterConfig()
        assert c.scrape_interval_seconds == 15
        assert c.namespace == "pvsolar"
        assert c.collectors == {}
        assert c.debug is False

    def test_with_collectors(self):
        collectors = {
            "gateway": CollectorConfig(url="http://localhost:8000"),
            "analytics": CollectorConfig(url="http://localhost:8001"),
        }
        c = ExporterConfig(collectors=collectors)
        assert len(c.collectors) == 2


class TestLoadConfig:
    def test_load_default(self):
        c = load_config()
        assert isinstance(c, ExporterConfig)

    def test_load_nonexistent(self):
        c = load_config("nonexistent.yaml")
        assert isinstance(c, ExporterConfig)

    def test_load_via_env_pvsolar_config(self, tmp_path, monkeypatch):
        cfg = tmp_path / "custom.yaml"
        cfg.write_text('company_name: "EXPORTER_VIA_ENV"\n', encoding="utf-8")
        monkeypatch.setenv("PVSOLAR_CONFIG", str(cfg))
        c = load_config()
        assert c.company_name == "EXPORTER_VIA_ENV"
