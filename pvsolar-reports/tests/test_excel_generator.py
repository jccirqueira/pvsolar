"""
Tests for pvSolar Reports Excel Generator.
"""

import os
import tempfile
import pytest
from src.generators.excel_generator import ExcelReportGenerator


class TestExcelReportGenerator:
    def setup_method(self):
        self.generator = ExcelReportGenerator(
            company_name="Test Company",
            primary_color="#10B981",
        )

    def test_create_generator(self):
        gen = ExcelReportGenerator()
        assert gen.company_name == "pvSolar Energy"

    def test_create_generator_custom(self):
        gen = ExcelReportGenerator(company_name="My Company", primary_color="#FF0000")
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
                {"name": "Inv 1", "power_kw": 20.0, "energy_kwh": 100.0, "dc_voltage": 600.0, "ac_voltage": 220.0, "temperature": 45.0, "status": "online"},
                {"name": "Inv 2", "power_kw": 18.5, "energy_kwh": 95.0, "dc_voltage": 595.0, "ac_voltage": 221.0, "temperature": 42.0, "status": "online"},
            ],
            "alarms": [
                {"timestamp": "2026-09-17T12:45:00", "level": "warning", "source": "Inv 3", "message": "High temp", "acknowledged": False},
            ],
            "performance": {
                "pr": 82.5,
                "cef": 95.0,
                "availability": 99.2,
                "efficiency": 97.5,
                "overall_score": 85.0,
                "grade": "A",
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "daily_report.xlsx")
            result = self.generator.generate_daily_report(data, output_path)
            assert os.path.exists(result)
            assert result.endswith(".xlsx")

    def test_generate_daily_report_no_data(self):
        data = {
            "date": "2026-09-17",
            "plant_name": "Test Plant",
            "plant": {"total_energy_kwh": 0, "total_power_kw": 0, "active_inverters": 0, "total_inverters": 0},
            "inverters": [],
            "alarms": [],
            "performance": None,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "daily_empty.xlsx")
            result = self.generator.generate_daily_report(data, output_path)
            assert os.path.exists(result)

    def test_generate_weekly_report(self):
        data = {
            "period": "2026-09-10 to 2026-09-17",
            "daily_data": [
                {"date": "2026-09-10", "plant": {"total_energy_kwh": 450.0, "total_power_kw": 90.0, "active_inverters": 5, "total_inverters": 6}, "alarms": []},
                {"date": "2026-09-11", "plant": {"total_energy_kwh": 520.0, "total_power_kw": 95.0, "active_inverters": 6, "total_inverters": 6}, "alarms": []},
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "weekly_report.xlsx")
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
            output_path = os.path.join(tmpdir, "monthly_report.xlsx")
            result = self.generator.generate_monthly_report(data, output_path)
            assert os.path.exists(result)

    def test_generate_maintenance_report(self):
        data = {
            "maintenance": {
                "predictions": [
                    {"component": "Inverter 2", "risk_level": "high", "horizon": "30d", "recommended_action": "Schedule inspection"},
                ],
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "maintenance_report.xlsx")
            result = self.generator.generate_maintenance_report(data, output_path)
            assert os.path.exists(result)
