"""
Tests for pvSolar Reports Configuration.
"""

from src.core.config import (
    AnalyticsConfig,
    APIConfig,
    EmailConfig,
    GatewayConfig,
    OutputConfig,
    OutputFormat,
    PlantConfig,
    ReportLanguage,
    ReportsConfig,
    ReportType,
    SchedulerConfig,
    TemplateConfig,
    load_config,
)


class TestGatewayConfig:
    def test_default_values(self):
        config = GatewayConfig()
        assert config.url == "http://localhost:8000"
        assert config.timeout == 30

    def test_custom_values(self):
        config = GatewayConfig(url="http://192.168.1.100:8000", api_key="test", timeout=60)
        assert config.url == "http://192.168.1.100:8000"
        assert config.api_key == "test"
        assert config.timeout == 60


class TestAnalyticsConfig:
    def test_default_values(self):
        config = AnalyticsConfig()
        assert config.url == "http://localhost:8001"
        assert config.timeout == 30


class TestEmailConfig:
    def test_default_values(self):
        config = EmailConfig()
        assert config.enabled is False
        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.use_tls is True

    def test_custom_values(self):
        config = EmailConfig(enabled=True, smtp_host="smtp.office365.com", recipients=["test@example.com"])
        assert config.enabled is True
        assert config.smtp_host == "smtp.office365.com"
        assert "test@example.com" in config.recipients


class TestSchedulerConfig:
    def test_default_values(self):
        config = SchedulerConfig()
        assert config.enabled is True
        assert config.daily_time == "06:00"
        assert config.weekly_day == 1
        assert config.monthly_day == 1


class TestOutputConfig:
    def test_default_values(self):
        config = OutputConfig()
        assert config.base_dir == "output"
        assert config.pdf_dir == "output/pdf"
        assert config.excel_dir == "output/excel"
        assert config.retention_days == 90


class TestTemplateConfig:
    def test_default_values(self):
        config = TemplateConfig()
        assert config.language == ReportLanguage.PT_BR
        assert config.company_name == "pvSolar Energy"
        assert config.primary_color == "#10B981"


class TestPlantConfig:
    def test_default_values(self):
        config = PlantConfig()
        assert config.name == "Solar Plant"
        assert config.capacity_kw == 100.0
        assert config.num_inverters == 1


class TestAPIConfig:
    def test_default_values(self):
        config = APIConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8002


class TestReportsConfig:
    def test_default_values(self):
        config = ReportsConfig()
        assert isinstance(config.gateway, GatewayConfig)
        assert isinstance(config.analytics, AnalyticsConfig)
        assert isinstance(config.email, EmailConfig)
        assert isinstance(config.scheduler, SchedulerConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.template, TemplateConfig)
        assert isinstance(config.plant, PlantConfig)
        assert isinstance(config.api, APIConfig)
        assert config.debug is False

    def test_formats_default(self):
        config = ReportsConfig()
        assert OutputFormat.PDF in config.formats
        assert OutputFormat.EXCEL in config.formats

    def test_report_types_default(self):
        config = ReportsConfig()
        assert ReportType.DAILY in config.report_types
        assert ReportType.WEEKLY in config.report_types
        assert ReportType.MONTHLY in config.report_types


class TestLoadConfig:
    def test_load_default(self):
        config = load_config()
        assert isinstance(config, ReportsConfig)

    def test_load_nonexistent_file(self):
        config = load_config("nonexistent.yaml")
        assert isinstance(config, ReportsConfig)

    def test_load_via_env_pvsolar_config(self, tmp_path, monkeypatch):
        cfg = tmp_path / "custom.yaml"
        cfg.write_text('plant:\n  name: "RELATORIO_VIA_ENV"\n', encoding="utf-8")
        monkeypatch.setenv("PVSOLAR_CONFIG", str(cfg))
        config = load_config()
        assert config.plant.name == "RELATORIO_VIA_ENV"


class TestEnums:
    def test_report_type_values(self):
        assert ReportType.DAILY == "daily"
        assert ReportType.WEEKLY == "weekly"
        assert ReportType.MONTHLY == "monthly"
        assert ReportType.MAINTENANCE == "maintenance"

    def test_output_format_values(self):
        assert OutputFormat.PDF == "pdf"
        assert OutputFormat.EXCEL == "excel"
        assert OutputFormat.HTML == "html"
        assert OutputFormat.ALL == "all"

    def test_language_values(self):
        assert ReportLanguage.PT_BR == "pt_BR"
        assert ReportLanguage.EN_US == "en_US"
