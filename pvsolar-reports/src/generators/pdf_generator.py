"""
PDF Report Generator.

Generates professional PDF reports using ReportLab.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    HRFlowable,
)

logger = structlog.get_logger(__name__)


class PDFReportGenerator:
    """
    Generates professional PDF reports.

    Features:
    - Custom company branding
    - Charts embedded as images
    - Multi-page support
    - Table of contents
    - Header/footer with page numbers
    """

    def __init__(
        self,
        company_name: str = "pvSolar Energy",
        primary_color: str = "#10B981",
        secondary_color: str = "#3B82F6",
        logo_path: Optional[str] = None,
    ):
        self.company_name = company_name
        self.primary_color = colors.HexColor(primary_color)
        self.secondary_color = colors.HexColor(secondary_color)
        self.logo_path = logo_path
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self) -> None:
        self.styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=self.styles["Title"],
            fontSize=24,
            spaceAfter=30,
            textColor=self.primary_color,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            parent=self.styles["Heading1"],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=self.primary_color,
            borderWidth=0,
            borderPadding=0,
        ))
        self.styles.add(ParagraphStyle(
            name="SubSection",
            parent=self.styles["Heading2"],
            fontSize=13,
            spaceBefore=15,
            spaceAfter=8,
            textColor=self.secondary_color,
        ))
        self.styles.add(ParagraphStyle(
            name="KPIValue",
            parent=self.styles["Normal"],
            fontSize=20,
            alignment=TA_CENTER,
            textColor=self.primary_color,
            fontName="Helvetica-Bold",
        ))
        self.styles.add(ParagraphStyle(
            name="KPILabel",
            parent=self.styles["Normal"],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.gray,
        ))
        self.styles.add(ParagraphStyle(
            name="SmallText",
            parent=self.styles["Normal"],
            fontSize=8,
            textColor=colors.gray,
        ))

    def _header_footer(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.gray)
        canvas.drawString(2*cm, A4[1] - 1*cm, self.company_name)
        canvas.drawRightString(A4[0] - 2*cm, A4[1] - 1*cm, f"Page {doc.page}")
        canvas.line(2*cm, A4[1] - 1.2*cm, A4[0] - 2*cm, A4[1] - 1.2*cm)
        canvas.drawString(2*cm, 1*cm, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        canvas.drawRightString(A4[0] - 2*cm, 1*cm, "pvSolar Reports v1.0.0")
        canvas.restoreState()

    def _make_table(self, headers: List[str], rows: List[List[str]], col_widths: Optional[List[float]] = None) -> Table:
        data = [headers] + rows
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.primary_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            ("TOPPADDING", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return table

    def _make_kpi_row(self, kpis: List[Dict[str, Any]]) -> Table:
        cells = []
        for kpi in kpis:
            cell = [
                Paragraph(str(kpi.get("value", "--")), self.styles["KPIValue"]),
                Paragraph(kpi.get("label", ""), self.styles["KPILabel"]),
            ]
            cells.append(cell)

        table = Table([cells], colWidths=[14 * cm / len(kpis)] * len(kpis))
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
            ("TOPPADDING", (0, 0), (-1, -1), 15),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
        ]))
        return table

    def generate_daily_report(self, data: Dict[str, Any], output_path: str) -> str:
        """Generate a daily report PDF."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        elements = []
        plant = data.get("plant", {})
        performance = data.get("performance")
        inverters = data.get("inverters", [])
        alarms = data.get("alarms", [])
        anomalies = data.get("anomalies", [])
        forecast = data.get("forecast")

        elements.append(Paragraph("Daily Report", self.styles["ReportTitle"]))
        elements.append(Paragraph(f"Plant: {data.get('plant_name', 'Solar Plant')}", self.styles["SubSection"]))
        elements.append(Paragraph(f"Date: {data.get('date', datetime.now().strftime('%Y-%m-%d'))}", self.styles["SubSection"]))
        elements.append(Spacer(1, 20))

        elements.append(Paragraph("Executive Summary", self.styles["SectionHeader"]))
        kpis = [
            {"label": "Energy (kWh)", "value": f"{plant.get('total_energy_kwh', 0):.1f}"},
            {"label": "Peak Power (kW)", "value": f"{plant.get('total_power_kw', 0):.1f}"},
            {"label": "Active Inverters", "value": f"{plant.get('active_inverters', 0)}/{plant.get('total_inverters', 0)}"},
        ]
        if performance:
            kpis.append({"label": "PR (%)", "value": f"{performance.get('pr', 0):.1f}"})
            kpis.append({"label": "Grade", "value": performance.get("grade", "--")})
        elements.append(self._make_kpi_row(kpis))
        elements.append(Spacer(1, 20))

        if inverters:
            elements.append(Paragraph("Inverter Performance", self.styles["SectionHeader"]))
            headers = ["Inverter", "Power (kW)", "Energy (kWh)", "Status", "Temp (°C)"]
            rows = []
            for inv in inverters:
                rows.append([
                    inv.get("name", "N/A"),
                    f"{inv.get('power_kw', 0):.1f}",
                    f"{inv.get('energy_kwh', 0):.1f}",
                    inv.get("status", "unknown"),
                    f"{inv.get('temperature', 0):.1f}",
                ])
            elements.append(self._make_table(headers, rows))
            elements.append(Spacer(1, 15))

        if alarms:
            elements.append(Paragraph("Alarms & Events", self.styles["SectionHeader"]))
            headers = ["Time", "Level", "Source", "Message"]
            rows = []
            for alarm in alarms[:20]:
                rows.append([
                    alarm.get("timestamp", "")[:19],
                    alarm.get("level", ""),
                    alarm.get("source", ""),
                    alarm.get("message", "")[:50],
                ])
            elements.append(self._make_table(headers, rows))
            elements.append(Spacer(1, 15))

        if performance and performance.get("recommendations"):
            elements.append(Paragraph("Recommendations", self.styles["SectionHeader"]))
            for i, rec in enumerate(performance["recommendations"], 1):
                elements.append(Paragraph(f"{i}. {rec}", self.styles["Normal"]))

        if forecast:
            elements.append(Spacer(1, 15))
            elements.append(Paragraph("Forecast", self.styles["SectionHeader"]))
            predicted = forecast.get("predicted_energy_kwh", 0)
            elements.append(Paragraph(
                f"Predicted energy for tomorrow: <b>{predicted:.1f} kWh</b>",
                self.styles["Normal"],
            ))

        doc.build(elements, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        logger.info("pdf.generated", path=str(path), pages=doc.page)
        return str(path)

    def generate_weekly_report(self, data: Dict[str, Any], output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        elements = []

        elements.append(Paragraph("Weekly Report", self.styles["ReportTitle"]))
        elements.append(Paragraph(f"Period: {data.get('period', '')}", self.styles["SubSection"]))
        elements.append(Spacer(1, 20))

        daily_data = data.get("daily_data", [])
        if daily_data:
            elements.append(Paragraph("Daily Production", self.styles["SectionHeader"]))
            headers = ["Date", "Energy (kWh)", "Peak Power (kW)", "Inverters", "Alarms"]
            rows = []
            for day in daily_data:
                plant = day.get("plant", {})
                rows.append([
                    day.get("date", ""),
                    f"{plant.get('total_energy_kwh', 0):.1f}",
                    f"{plant.get('total_power_kw', 0):.1f}",
                    f"{plant.get('active_inverters', 0)}/{plant.get('total_inverters', 0)}",
                    str(len(day.get("alarms", []))),
                ])
            elements.append(self._make_table(headers, rows))

        doc.build(elements, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        logger.info("pdf.weekly_generated", path=str(path))
        return str(path)

    def generate_monthly_report(self, data: Dict[str, Any], output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        elements = []

        elements.append(Paragraph("Monthly Report", self.styles["ReportTitle"]))
        elements.append(Paragraph(f"Period: {data.get('period', '')}", self.styles["SubSection"]))
        elements.append(Spacer(1, 20))

        daily_data = data.get("daily_data", [])
        if daily_data:
            total_energy = sum(d.get("plant", {}).get("total_energy_kwh", 0) for d in daily_data)
            avg_daily = total_energy / len(daily_data) if daily_data else 0
            elements.append(Paragraph("Monthly Summary", self.styles["SectionHeader"]))
            kpis = [
                {"label": "Total Energy (kWh)", "value": f"{total_energy:.1f}"},
                {"label": "Avg Daily (kWh)", "value": f"{avg_daily:.1f}"},
                {"label": "Days", "value": str(len(daily_data))},
            ]
            elements.append(self._make_kpi_row(kpis))
            elements.append(Spacer(1, 15))

            elements.append(Paragraph("Daily Production", self.styles["SectionHeader"]))
            headers = ["Date", "Energy (kWh)", "Peak Power (kW)", "Alarms"]
            rows = []
            for day in daily_data:
                plant = day.get("plant", {})
                rows.append([
                    day.get("date", ""),
                    f"{plant.get('total_energy_kwh', 0):.1f}",
                    f"{plant.get('total_power_kw', 0):.1f}",
                    str(len(day.get("alarms", []))),
                ])
            elements.append(self._make_table(headers, rows))

        doc.build(elements, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        logger.info("pdf.monthly_generated", path=str(path))
        return str(path)

    def generate_maintenance_report(self, data: Dict[str, Any], output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        elements = []

        elements.append(Paragraph("Maintenance Report", self.styles["ReportTitle"]))
        elements.append(Spacer(1, 20))

        maintenance = data.get("maintenance", {})
        if maintenance:
            elements.append(Paragraph("Risk Assessment", self.styles["SectionHeader"]))
            risk = maintenance.get("risk_level", "low")
            risk_color = {"low": "#10B981", "medium": "#F59E0B", "high": "#EF4444"}.get(risk, "#6B7280")
            elements.append(Paragraph(
                f"Overall Risk Level: <font color='{risk_color}'><b>{risk.upper()}</b></font>",
                self.styles["Normal"],
            ))
            elements.append(Spacer(1, 15))

            if maintenance.get("urgent_actions"):
                elements.append(Paragraph("Urgent Actions", self.styles["SectionHeader"]))
                for action in maintenance["urgent_actions"]:
                    elements.append(Paragraph(f"• {action}", self.styles["Normal"]))

            predictions = maintenance.get("predictions", [])
            if predictions:
                elements.append(Paragraph("Predictions", self.styles["SectionHeader"]))
                headers = ["Component", "Risk", "Horizon", "Action"]
                rows = []
                for pred in predictions[:15]:
                    rows.append([
                        pred.get("component", "N/A"),
                        pred.get("risk_level", "low"),
                        pred.get("horizon", "N/A"),
                        pred.get("recommended_action", "N/A")[:40],
                    ])
                elements.append(self._make_table(headers, rows))

        doc.build(elements, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        logger.info("pdf.maintenance_generated", path=str(path))
        return str(path)
