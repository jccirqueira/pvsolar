"""Testes do quality_analyzer do pvSolar Grid."""

import pytest
from src.core.config import ComplianceStatus, PRODISTLimits, QualityMetric
from src.quality.quality_analyzer import QualityAnalyzer


class TestQualityAnalyzer:
    def test_create_analyzer(self):
        a = QualityAnalyzer()
        assert len(a.measurements) == 0

    def test_analyze_thd_voltage_ok(self):
        a = QualityAnalyzer()
        m = a.analyze_thd_voltage(5.0)
        assert m.compliance == ComplianceStatus.COMPLIANT

    def test_analyze_thd_voltage_high(self):
        a = QualityAnalyzer()
        m = a.analyze_thd_voltage(10.0)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_thd_current_ok(self):
        a = QualityAnalyzer()
        m = a.analyze_thd_current(3.0)
        assert m.compliance == ComplianceStatus.COMPLIANT

    def test_analyze_thd_current_high(self):
        a = QualityAnalyzer()
        m = a.analyze_thd_current(7.0)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_voltage_ok(self):
        a = QualityAnalyzer()
        m = a.analyze_voltage(1.0)
        assert m.compliance == ComplianceStatus.COMPLIANT

    def test_analyze_voltage_low(self):
        a = QualityAnalyzer()
        m = a.analyze_voltage(0.8)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_voltage_high(self):
        a = QualityAnalyzer()
        m = a.analyze_voltage(1.15)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_power_factor_ok(self):
        a = QualityAnalyzer()
        m = a.analyze_power_factor(0.95)
        assert m.compliance == ComplianceStatus.COMPLIANT

    def test_analyze_power_factor_low(self):
        a = QualityAnalyzer()
        m = a.analyze_power_factor(0.85)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_frequency_ok(self):
        a = QualityAnalyzer()
        m = a.analyze_frequency(60.0)
        assert m.compliance == ComplianceStatus.COMPLIANT

    def test_analyze_frequency_low(self):
        a = QualityAnalyzer()
        m = a.analyze_frequency(59.0)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_flicker_ok(self):
        a = QualityAnalyzer()
        m = a.analyze_flicker(0.5)
        assert m.compliance == ComplianceStatus.COMPLIANT

    def test_analyze_flicker_high(self):
        a = QualityAnalyzer()
        m = a.analyze_flicker(1.5)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_unbalance_ok(self):
        a = QualityAnalyzer()
        m = a.analyze_unbalance(1.0)
        assert m.compliance == ComplianceStatus.COMPLIANT

    def test_analyze_unbalance_high(self):
        a = QualityAnalyzer()
        m = a.analyze_unbalance(3.0)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_reactive_power_ok(self):
        a = QualityAnalyzer()
        m = a.analyze_reactive_power(100.0, 200.0)
        assert m.compliance == ComplianceStatus.COMPLIANT

    def test_analyze_reactive_power_high(self):
        a = QualityAnalyzer()
        m = a.analyze_reactive_power(250.0, 200.0)
        assert m.compliance == ComplianceStatus.NON_COMPLIANT

    def test_analyze_all(self):
        a = QualityAnalyzer()
        results = a.analyze_all({
            "thd_v": 5.0,
            "voltage_pu": 1.0,
            "power_factor": 0.95,
            "frequency": 60.0,
        })
        assert len(results) == 4

    def test_get_measurements_by_metric(self):
        a = QualityAnalyzer()
        a.analyze_thd_voltage(5.0)
        a.analyze_thd_voltage(6.0)
        a.analyze_voltage(1.0)
        thd = a.get_measurements_by_metric(QualityMetric.THD_V)
        assert len(thd) == 2

    def test_get_non_compliant(self):
        a = QualityAnalyzer()
        a.analyze_thd_voltage(5.0)
        a.analyze_thd_voltage(10.0)
        nc = a.get_non_compliant()
        assert len(nc) == 1

    def test_get_compliance_rate(self):
        a = QualityAnalyzer()
        a.analyze_thd_voltage(5.0)
        a.analyze_thd_voltage(10.0)
        assert a.get_compliance_rate() == 50.0

    def test_get_statistics(self):
        a = QualityAnalyzer()
        a.analyze_thd_voltage(5.0)
        stats = a.get_statistics()
        assert stats["total_measurements"] == 1

    def test_clear(self):
        a = QualityAnalyzer()
        a.analyze_thd_voltage(5.0)
        count = a.clear()
        assert count == 1
        assert len(a.measurements) == 0
