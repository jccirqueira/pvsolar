"""Testes do compliance_engine do pvSolar Grid."""

import pytest

from src.core.config import ComplianceStatus, GridStandard, PRODISTLimits
from src.compliance.compliance_engine import ComplianceCheck, ComplianceEngine


class TestComplianceCheck:
    def test_create_check(self):
        c = ComplianceCheck(name="Voltage", status=ComplianceStatus.COMPLIANT)
        assert c.name == "Voltage"
        assert c.status == ComplianceStatus.COMPLIANT

    def test_to_dict(self):
        c = ComplianceCheck(name="THD", actual_value=5.0, limit_value=8.0)
        d = c.to_dict()
        assert d["name"] == "THD"
        assert d["actual_value"] == 5.0


class TestComplianceEngine:
    def test_create_engine(self):
        e = ComplianceEngine()
        assert len(e.checks) == 0

    def test_check_voltage_compliant(self):
        e = ComplianceEngine()
        c = e.check_voltage(1.0)
        assert c.status == ComplianceStatus.COMPLIANT

    def test_check_voltage_low(self):
        e = ComplianceEngine()
        c = e.check_voltage(0.8)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_check_voltage_high(self):
        e = ComplianceEngine()
        c = e.check_voltage(1.15)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_check_thd_voltage_ok(self):
        e = ComplianceEngine()
        c = e.check_thd_voltage(5.0)
        assert c.status == ComplianceStatus.COMPLIANT

    def test_check_thd_voltage_high(self):
        e = ComplianceEngine()
        c = e.check_thd_voltage(10.0)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_check_thd_current_ok(self):
        e = ComplianceEngine()
        c = e.check_thd_current(3.0)
        assert c.status == ComplianceStatus.COMPLIANT

    def test_check_thd_current_high(self):
        e = ComplianceEngine()
        c = e.check_thd_current(7.0)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_check_power_factor_ok(self):
        e = ComplianceEngine()
        c = e.check_power_factor(0.95)
        assert c.status == ComplianceStatus.COMPLIANT

    def test_check_power_factor_low(self):
        e = ComplianceEngine()
        c = e.check_power_factor(0.85)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_check_frequency_ok(self):
        e = ComplianceEngine()
        c = e.check_frequency(60.0)
        assert c.status == ComplianceStatus.COMPLIANT

    def test_check_frequency_low(self):
        e = ComplianceEngine()
        c = e.check_frequency(59.0)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_check_frequency_high(self):
        e = ComplianceEngine()
        c = e.check_frequency(61.0)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_check_flicker_ok(self):
        e = ComplianceEngine()
        c = e.check_flicker(0.5)
        assert c.status == ComplianceStatus.COMPLIANT

    def test_check_flicker_high(self):
        e = ComplianceEngine()
        c = e.check_flicker(1.5)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_check_unbalance_ok(self):
        e = ComplianceEngine()
        c = e.check_unbalance(1.0)
        assert c.status == ComplianceStatus.COMPLIANT

    def test_check_unbalance_high(self):
        e = ComplianceEngine()
        c = e.check_unbalance(3.0)
        assert c.status == ComplianceStatus.NON_COMPLIANT

    def test_run_full_check(self):
        e = ComplianceEngine()
        checks = e.run_full_check({
            "voltage_pu": 1.0,
            "thd_v": 5.0,
            "power_factor": 0.95,
            "frequency": 60.0,
        })
        assert len(checks) == 4

    def test_get_overall_status_compliant(self):
        e = ComplianceEngine()
        e.check_voltage(1.0)
        e.check_thd_voltage(5.0)
        assert e.get_overall_status() == ComplianceStatus.COMPLIANT

    def test_get_overall_status_non_compliant(self):
        e = ComplianceEngine()
        e.check_voltage(1.0)
        e.check_thd_voltage(10.0)
        assert e.get_overall_status() == ComplianceStatus.NON_COMPLIANT

    def test_get_score(self):
        e = ComplianceEngine()
        e.check_voltage(1.0)
        e.check_thd_voltage(5.0)
        assert e.get_score() == 100.0

    def test_get_score_partial(self):
        e = ComplianceEngine()
        e.check_voltage(1.0)
        e.check_thd_voltage(10.0)
        assert e.get_score() == 50.0

    def test_generate_report(self):
        e = ComplianceEngine()
        e.check_voltage(1.0)
        r = e.generate_report("2024-01-01", "2024-01-31", GridStandard.PRODIST)
        assert r.score == 100.0
        assert len(e.reports) == 1

    def test_get_check_history(self):
        e = ComplianceEngine()
        e.check_voltage(1.0)
        e.check_voltage(0.8)
        history = e.get_check_history("Tensão PCC")
        assert len(history) == 2

    def test_get_statistics(self):
        e = ComplianceEngine()
        e.check_voltage(1.0)
        e.check_thd_voltage(10.0)
        stats = e.get_statistics()
        assert stats["total_checks"] == 2

    def test_clear(self):
        e = ComplianceEngine()
        e.check_voltage(1.0)
        count = e.clear()
        assert count == 1
        assert len(e.checks) == 0
