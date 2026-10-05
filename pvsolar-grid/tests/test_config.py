"""Testes do módulo config do pvSolar Grid."""

from pathlib import Path

import pytest

from src.core.config import (
    ComplianceStatus,
    EventRecord,
    FaultType,
    FRTConfig,
    GridConfig,
    GridConnectionConfig,
    GridStandard,
    HVRTCurve,
    LVRTCurve,
    PRODISTLimits,
    QualityMeasurement,
    QualityMetric,
    ReportType,
    VoltageLevel,
    load_config,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestGridStandard:
    def test_prodist(self):
        assert GridStandard.PRODIST == "prodist"
    def test_aneel(self):
        assert GridStandard.ANEEL == "aneel"
    def test_inmetro(self):
        assert GridStandard.INMETRO == "inmetro"
    def test_ons(self):
        assert GridStandard.ONS == "ons"


class TestVoltageLevel:
    def test_low(self):
        assert VoltageLevel.LOW == "low"
    def test_medium(self):
        assert VoltageLevel.MEDIUM == "medium"
    def test_high(self):
        assert VoltageLevel.HIGH == "high"
    def test_extra_high(self):
        assert VoltageLevel.EXTRA_HIGH == "extra_high"


class TestComplianceStatus:
    def test_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"
    def test_non_compliant(self):
        assert ComplianceStatus.NON_COMPLIANT == "non_compliant"
    def test_warning(self):
        assert ComplianceStatus.WARNING == "warning"
    def test_unknown(self):
        assert ComplianceStatus.UNKNOWN == "unknown"


class TestFaultType:
    def test_lvrt(self):
        assert FaultType.LVRT == "lvrt"
    def test_hvrt(self):
        assert FaultType.HVRT == "hvrt"
    def test_frt(self):
        assert FaultType.FRT == "frt"
    def test_frequency(self):
        assert FaultType.FREQUENCY == "frequency"


class TestQualityMetric:
    def test_thd_v(self):
        assert QualityMetric.THD_V == "thd_v"
    def test_thd_i(self):
        assert QualityMetric.THD_I == "thd_i"
    def test_pcc_voltage(self):
        assert QualityMetric.PCC_VOLTAGE == "pcc_voltage"
    def test_power_factor(self):
        assert QualityMetric.POWER_FACTOR == "power_factor"
    def test_frequency(self):
        assert QualityMetric.FREQUENCY == "frequency"


class TestReportType:
    def test_daily(self):
        assert ReportType.DAILY == "daily"
    def test_monthly(self):
        assert ReportType.MONTHLY == "monthly"


# ---------------------------------------------------------------------------
# Config Models
# ---------------------------------------------------------------------------

class TestPRODISTLimits:
    def test_defaults(self):
        l = PRODISTLimits()
        assert l.voltage_min_pu == 0.9
        assert l.voltage_max_pu == 1.1
        assert l.thd_v_max == 8.0
        assert l.thd_i_max == 5.0
        assert l.power_factor_min == 0.925
        assert l.frequency_min == 59.5
        assert l.frequency_max == 60.5


class TestLVRTCurve:
    def test_create(self):
        c = LVRTCurve(time_ms=0.0, voltage_pu=0.0)
        assert c.time_ms == 0.0
        assert c.voltage_pu == 0.0


class TestHVRTCurve:
    def test_create(self):
        c = HVRTCurve(time_ms=0.0, voltage_pu=1.2)
        assert c.voltage_pu == 1.2


class TestFRTConfig:
    def test_defaults(self):
        f = FRTConfig()
        assert f.enabled is True
        assert f.reconnect_time_ms == 2000.0


class TestGridConnectionConfig:
    def test_defaults(self):
        g = GridConnectionConfig()
        assert g.nominal_voltage_kv == 13.8
        assert g.nominal_frequency == 60.0
        assert g.voltage_level == VoltageLevel.MEDIUM


class TestEventRecord:
    def test_create(self):
        e = EventRecord(id="e1", event_type=FaultType.LVRT)
        assert e.event_type == FaultType.LVRT
    def test_to_dict(self):
        e = EventRecord(id="e1", event_type=FaultType.HVRT)
        d = e.to_dict()
        assert d["event_type"] == "hvrt"


class TestQualityMeasurement:
    def test_create(self):
        m = QualityMeasurement(metric=QualityMetric.THD_V, value=5.0)
        assert m.value == 5.0
    def test_to_dict(self):
        m = QualityMeasurement(metric=QualityMetric.POWER_FACTOR, value=0.95)
        d = m.to_dict()
        assert d["metric"] == "power_factor"


class TestGridConfig:
    def test_defaults(self):
        c = GridConfig()
        assert c.company_name == "pvSolar Grid"
        assert c.debug is False
        assert c.api.port == 8005
    def test_with_site(self):
        c = GridConfig(site_id="site_1")
        assert c.site_id == "site_1"


# ---------------------------------------------------------------------------
# Load Config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_default(self):
        c = load_config()
        assert c.company_name == "pvSolar Grid"
    def test_load_nonexistent(self):
        c = load_config("/nonexistent/path.yaml")
        assert c.company_name == "pvSolar Grid"
    def test_load_yaml(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text(
            "company_name: TestCo\ndebug: true\napi:\n  port: 9000\n"
        )
        c = load_config(config_file)
        assert c.company_name == "TestCo"
        assert c.debug is True
        assert c.api.port == 9000
