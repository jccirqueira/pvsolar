"""Testes do report_generator do pvSolar Grid."""

import pytest
from src.core.config import ComplianceStatus, GridStandard
from src.reports.report_generator import GridReport, ReportGenerator, ReportSection


class TestReportSection:
    def test_create_section(self):
        s = ReportSection(title="Test", content="Content")
        assert s.title == "Test"
        assert s.content == "Content"


class TestGridReport:
    def test_create_report(self):
        r = GridReport(site_id="site_1")
        assert r.site_id == "site_1"
    def test_to_dict(self):
        r = GridReport(site_id="site_1", period_start="2024-01-01")
        d = r.to_dict()
        assert d["site_id"] == "site_1"


class TestReportGenerator:
    def test_create_generator(self):
        g = ReportGenerator()
        assert len(g.reports) == 0

    def test_generate_compliance_report(self):
        g = ReportGenerator()
        r = g.generate_compliance_report(
            site_id="site_1",
            period_start="2024-01-01",
            period_end="2024-01-31",
            standard=GridStandard.PRODIST,
            compliance_checks=[
                {"name": "Voltage", "status": "compliant", "message": "OK"},
                {"name": "THD", "status": "non_compliant", "message": "High"},
            ],
            score=50.0,
        )
        assert r.summary["score"] == 50.0
        assert len(g.reports) == 1

    def test_generate_quality_report(self):
        g = ReportGenerator()
        r = g.generate_quality_report(
            site_id="site_1",
            period_start="2024-01-01",
            period_end="2024-01-31",
            measurements=[
                {"metric": "thd_v", "value": 5.0, "compliance": "compliant"},
            ],
        )
        assert r.site_id == "site_1"
        assert len(g.reports) == 1

    def test_generate_fault_report(self):
        g = ReportGenerator()
        r = g.generate_fault_report(
            site_id="site_1",
            period_start="2024-01-01",
            period_end="2024-01-31",
            events=[
                {"event_type": "frt", "compliance": "compliant"},
            ],
        )
        assert r.site_id == "site_1"

    def test_get_report(self):
        g = ReportGenerator()
        r = g.generate_compliance_report(
            "site_1", "2024-01-01", "2024-01-31",
            GridStandard.PRODIST, [], 100.0,
        )
        found = g.get_report(r.id)
        assert found is not None
        assert found.id == r.id

    def test_get_report_none(self):
        g = ReportGenerator()
        assert g.get_report("nonexistent") is None

    def test_get_reports_by_site(self):
        g = ReportGenerator()
        g.generate_compliance_report(
            "site_1", "2024-01-01", "2024-01-31",
            GridStandard.PRODIST, [], 100.0,
        )
        g.generate_compliance_report(
            "site_2", "2024-01-01", "2024-01-31",
            GridStandard.PRODIST, [], 100.0,
        )
        site1 = g.get_reports_by_site("site_1")
        assert len(site1) == 1

    def test_delete_report(self):
        g = ReportGenerator()
        r = g.generate_compliance_report(
            "site_1", "2024-01-01", "2024-01-31",
            GridStandard.PRODIST, [], 100.0,
        )
        assert g.delete_report(r.id) is True
        assert len(g.reports) == 0

    def test_delete_report_none(self):
        g = ReportGenerator()
        assert g.delete_report("nonexistent") is False

    def test_get_statistics(self):
        g = ReportGenerator()
        g.generate_compliance_report(
            "site_1", "2024-01-01", "2024-01-31",
            GridStandard.PRODIST, [], 100.0,
        )
        stats = g.get_statistics()
        assert stats["total_reports"] == 1

    def test_clear(self):
        g = ReportGenerator()
        g.generate_compliance_report(
            "site_1", "2024-01-01", "2024-01-31",
            GridStandard.PRODIST, [], 100.0,
        )
        count = g.clear()
        assert count == 1
        assert len(g.reports) == 0
