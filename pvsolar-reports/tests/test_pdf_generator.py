"""
Tests for pvSolar Reports PDF Generator.
"""

import os
import tempfile

from src.generators.pdf_generator import PDFReportGenerator


class TestPDFReportGenerator:
    def setup_method(self):
        self.generator = PDFReportGenerator(
            company_name="Test Company",
            primary_color="#10B981",
            secondary_color="#3B82F6",
        )

    def test_create_generator(self):
        gen = PDFReportGenerator()
        assert gen.company_name == "pvSolar Energy"
        assert gen.primary_color is not None

    def test_create_generator_custom(self):
        gen = PDFReportGenerator(company_name="My Company", primary_color="#FF0000")
        assert gen.company_name == "My Company"

    def test_generate_daily_report(self):
        data = {
            "date": "2026-09-17",
            "plant_name": "Test Plant",
            "plant": {
                "total_energy_kwh": 487.3,
                "total_power_kw": 98.2,
                "active_inverters": 5,
                "total_inverters": 6,
            },
            "inverters": [
                {"name": "Inv 1", "power_kw": 20.0, "energy_kwh": 100.0, "status": "online", "temperature": 45.0},
                {"name": "Inv 2", "power_kw": 18.5, "energy_kwh": 95.0, "status": "online", "temperature": 42.0},
            ],
            "alarms": [
                {"timestamp": "2026-09-17T12:45:00", "level": "warning", "source": "Inv 3", "message": "High temp"},
            ],
            "performance": {
                "pr": 82.5,
                "grade": "A",
                "recommendations": ["Clean panels on row 3"],
            },
            "anomalies": [],
            "forecast": {"predicted_energy_kwh": 510.0},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "daily_report.pdf")
            result = self.generator.generate_daily_report(data, output_path)
            assert os.path.exists(result)
            assert result.endswith(".pdf")

    def test_generate_weekly_report(self):
        data = {
            "period": "2026-09-10 to 2026-09-17",
            "daily_data": [
                {"date": "2026-09-10", "plant": {"total_energy_kwh": 450.0, "total_power_kw": 90.0, "active_inverters": 5, "total_inverters": 6}, "alarms": []},
                {"date": "2026-09-11", "plant": {"total_energy_kwh": 520.0, "total_power_kw": 95.0, "active_inverters": 6, "total_inverters": 6}, "alarms": []},
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "weekly_report.pdf")
            result = self.generator.generate_weekly_report(data, output_path)
            assert os.path.exists(result)

    def test_generate_monthly_report(self):
        data = {
            "period": "2026-09",
            "daily_data": [
                {"date": f"2026-09-{d:02d}", "plant": {"total_energy_kwh": 400.0 + d * 10, "total_power_kw": 85.0, "active_inverters": 5, "total_inverters": 6}, "alarms": []}
                for d in range(1, 16)
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "monthly_report.pdf")
            result = self.generator.generate_monthly_report(data, output_path)
            assert os.path.exists(result)

    def test_generate_maintenance_report(self):
        data = {
            "maintenance": {
                "risk_level": "medium",
                "urgent_actions": ["Clean inverter 3 filters"],
                "predictions": [
                    {"component": "Inverter 2", "risk_level": "high", "horizon": "30d", "recommended_action": "Schedule inspection"},
                    {"component": "Panel Row 5", "risk_level": "medium", "horizon": "60d", "recommended_action": "Clean panels"},
                ],
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "maintenance_report.pdf")
            result = self.generator.generate_maintenance_report(data, output_path)
            assert os.path.exists(result)

    def test_make_table(self):
        headers = ["Name", "Value"]
        rows = [["Power", "50 kW"], ["Energy", "400 kWh"]]
        table = self.generator._make_table(headers, rows)
        assert table is not None
