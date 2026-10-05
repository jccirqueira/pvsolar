"""
Excel Report Generator.

Generates Excel workbooks with charts using OpenPyXL.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

logger = structlog.get_logger(__name__)


class ExcelReportGenerator:
    """
    Generates Excel workbooks.

    Features:
    - Multiple worksheets
    - Embedded charts
    - Conditional formatting
    - Auto-sized columns
    - Custom colors and styles
    """

    def __init__(self, company_name: str = "pvSolar Energy", primary_color: str = "#10B981"):
        self.company_name = company_name
        self.primary_color = primary_color
        self._header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        self._header_fill = PatternFill(start_color=primary_color.replace("#", ""), end_color=primary_color.replace("#", ""), fill_type="solid")
        self._header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        self._border = Border(
            left=Side(style="thin", color="D1D5DB"),
            right=Side(style="thin", color="D1D5DB"),
            top=Side(style="thin", color="D1D5DB"),
            bottom=Side(style="thin", color="D1D5DB"),
        )

    def _style_header_row(self, ws, row: int, num_cols: int) -> None:
        for col in range(1, num_cols + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = self._header_font
            cell.fill = self._header_fill
            cell.alignment = self._header_alignment
            cell.border = self._border

    def _style_data_rows(self, ws, start_row: int, end_row: int, num_cols: int) -> None:
        for row in range(start_row, end_row + 1):
            for col in range(1, num_cols + 1):
                cell = ws.cell(row=row, column=col)
                cell.border = self._border
                cell.alignment = Alignment(horizontal="center", vertical="center")
                if row % 2 == 0:
                    cell.fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    def _auto_width(self, ws) -> None:
        for col in ws.columns:
            max_length = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass
            ws.column_dimensions[col_letter].width = min(max(max_length + 2, 10), 40)

    def generate_daily_report(self, data: Dict[str, Any], output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()

        # Summary sheet
        ws_summary = wb.active
        ws_summary.title = "Summary"
        plant = data.get("plant", {})
        performance = data.get("performance")

        summary_headers = ["Metric", "Value"]
        summary_data = [
            ["Report Date", data.get("date", "")],
            ["Plant Name", data.get("plant_name", "Solar Plant")],
            ["Total Energy (kWh)", f"{plant.get('total_energy_kwh', 0):.2f}"],
            ["Peak Power (kW)", f"{plant.get('total_power_kw', 0):.2f}"],
            ["Active Inverters", f"{plant.get('active_inverters', 0)}/{plant.get('total_inverters', 0)}"],
        ]
        if performance:
            summary_data.extend([
                ["Performance Ratio (%)", f"{performance.get('pr', 0):.2f}"],
                ["Cleanliness Factor (%)", f"{performance.get('cef', 0):.2f}"],
                ["Availability (%)", f"{performance.get('availability', 0):.2f}"],
                ["Efficiency (%)", f"{performance.get('efficiency', 0):.2f}"],
                ["Overall Score", f"{performance.get('overall_score', 0):.1f}"],
                ["Grade", performance.get("grade", "--")],
            ])

        ws_summary.append(summary_headers)
        for row in summary_data:
            ws_summary.append(row)
        self._style_header_row(ws_summary, 1, 2)
        self._style_data_rows(ws_summary, 2, len(summary_data) + 1, 2)
        self._auto_width(ws_summary)

        # Inverters sheet
        inverters = data.get("inverters", [])
        if inverters:
            ws_inv = wb.create_sheet("Inverters")
            inv_headers = ["Inverter", "Power (kW)", "Energy (kWh)", "DC Voltage (V)", "AC Voltage (V)", "Temperature (°C)", "Status"]
            ws_inv.append(inv_headers)
            for inv in inverters:
                ws_inv.append([
                    inv.get("name", "N/A"),
                    inv.get("power_kw", 0),
                    inv.get("energy_kwh", 0),
                    inv.get("dc_voltage", 0),
                    inv.get("ac_voltage", 0),
                    inv.get("temperature", 0),
                    inv.get("status", "unknown"),
                ])
            self._style_header_row(ws_inv, 1, len(inv_headers))
            self._style_data_rows(ws_inv, 2, len(inverters) + 1, len(inv_headers))
            self._auto_width(ws_inv)

            if len(inverters) > 1:
                chart = BarChart()
                chart.title = "Power by Inverter"
                chart.y_axis.title = "Power (kW)"
                chart.x_axis.title = "Inverter"
                data_ref = Reference(ws_inv, min_col=2, min_row=1, max_row=len(inverters) + 1)
                cats = Reference(ws_inv, min_col=1, min_row=2, max_row=len(inverters) + 1)
                chart.add_data(data_ref, titles_from_data=True)
                chart.set_categories(cats)
                chart.shape = 4
                ws_inv.add_chart(chart, "I2")

        # Alarms sheet
        alarms = data.get("alarms", [])
        if alarms:
            ws_alarm = wb.create_sheet("Alarms")
            alarm_headers = ["Time", "Level", "Source", "Message", "Acknowledged"]
            ws_alarm.append(alarm_headers)
            for alarm in alarms:
                ws_alarm.append([
                    alarm.get("timestamp", "")[:19],
                    alarm.get("level", ""),
                    alarm.get("source", ""),
                    alarm.get("message", ""),
                    "Yes" if alarm.get("acknowledged") else "No",
                ])
            self._style_header_row(ws_alarm, 1, len(alarm_headers))
            self._style_data_rows(ws_alarm, 2, len(alarms) + 1, len(alarm_headers))
            self._auto_width(ws_alarm)

        wb.save(str(path))
        logger.info("excel.generated", path=str(path))
        return str(path)

    def generate_weekly_report(self, data: Dict[str, Any], output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        ws = wb.active
        ws.title = "Weekly Production"

        headers = ["Date", "Energy (kWh)", "Peak Power (kW)", "Active Inverters", "Alarms"]
        ws.append(headers)

        daily_data = data.get("daily_data", [])
        for day in daily_data:
            plant = day.get("plant", {})
            ws.append([
                day.get("date", ""),
                plant.get("total_energy_kwh", 0),
                plant.get("total_power_kw", 0),
                plant.get("active_inverters", 0),
                len(day.get("alarms", [])),
            ])

        self._style_header_row(ws, 1, len(headers))
        self._style_data_rows(ws, 2, len(daily_data) + 1, len(headers))
        self._auto_width(ws)

        if daily_data:
            chart = LineChart()
            chart.title = "Weekly Energy Production"
            chart.y_axis.title = "Energy (kWh)"
            chart.x_axis.title = "Date"
            data_ref = Reference(ws, min_col=2, min_row=1, max_row=len(daily_data) + 1)
            cats = Reference(ws, min_col=1, min_row=2, max_row=len(daily_data) + 1)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats)
            chart.width = 20
            chart.height = 12
            ws.add_chart(chart, "G2")

        wb.save(str(path))
        logger.info("excel.weekly_generated", path=str(path))
        return str(path)

    def generate_monthly_report(self, data: Dict[str, Any], output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()

        # Summary
        ws_summary = wb.active
        ws_summary.title = "Monthly Summary"
        daily_data = data.get("daily_data", [])
        total_energy = sum(d.get("plant", {}).get("total_energy_kwh", 0) for d in daily_data)
        avg_daily = total_energy / len(daily_data) if daily_data else 0

        ws_summary.append(["Metric", "Value"])
        ws_summary.append(["Period", data.get("period", "")])
        ws_summary.append(["Total Energy (kWh)", f"{total_energy:.2f}"])
        ws_summary.append(["Average Daily (kWh)", f"{avg_daily:.2f}"])
        ws_summary.append(["Days in Period", str(len(daily_data))])
        self._style_header_row(ws_summary, 1, 2)
        self._style_data_rows(ws_summary, 2, 5, 2)
        self._auto_width(ws_summary)

        # Daily breakdown
        ws_daily = wb.create_sheet("Daily Breakdown")
        headers = ["Date", "Energy (kWh)", "Peak Power (kW)", "Alarms"]
        ws_daily.append(headers)
        for day in daily_data:
            plant = day.get("plant", {})
            ws_daily.append([
                day.get("date", ""),
                plant.get("total_energy_kwh", 0),
                plant.get("total_power_kw", 0),
                len(day.get("alarms", [])),
            ])
        self._style_header_row(ws_daily, 1, len(headers))
        self._style_data_rows(ws_daily, 2, len(daily_data) + 1, len(headers))
        self._auto_width(ws_daily)

        if daily_data:
            chart = BarChart()
            chart.title = "Monthly Energy Production"
            chart.y_axis.title = "Energy (kWh)"
            data_ref = Reference(ws_daily, min_col=2, min_row=1, max_row=len(daily_data) + 1)
            cats = Reference(ws_daily, min_col=1, min_row=2, max_row=len(daily_data) + 1)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats)
            ws_daily.add_chart(chart, "F2")

        wb.save(str(path))
        logger.info("excel.monthly_generated", path=str(path))
        return str(path)

    def generate_maintenance_report(self, data: Dict[str, Any], output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        ws = wb.active
        ws.title = "Maintenance"

        maintenance = data.get("maintenance", {})
        headers = ["Component", "Risk Level", "Horizon", "Recommended Action"]
        ws.append(headers)

        for pred in maintenance.get("predictions", []):
            ws.append([
                pred.get("component", "N/A"),
                pred.get("risk_level", "low"),
                pred.get("horizon", "N/A"),
                pred.get("recommended_action", "N/A"),
            ])

        self._style_header_row(ws, 1, len(headers))
        self._style_data_rows(ws, 2, len(maintenance.get("predictions", [])) + 1, len(headers))
        self._auto_width(ws)

        wb.save(str(path))
        logger.info("excel.maintenance_generated", path=str(path))
        return str(path)
