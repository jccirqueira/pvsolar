"""Gerador de relatórios de compliance."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from src.core.config import (
    ComplianceReport,
    ComplianceStatus,
    GridStandard,
    QualityMeasurement,
    EventRecord,
)

logger = structlog.get_logger()


@dataclass
class ReportSection:
    """Seção de um relatório."""

    title: str = ""
    content: str = ""
    items: list[dict] = field(default_factory=list)


@dataclass
class GridReport:
    """Relatório completo de grid."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    site_id: str = ""
    period_start: str = ""
    period_end: str = ""
    standard: GridStandard = GridStandard.PRODIST
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sections: list[ReportSection] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Converte para dict."""
        return {
            "id": self.id,
            "site_id": self.site_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "standard": self.standard.value,
            "generated_at": self.generated_at.isoformat(),
            "sections": [
                {"title": s.title, "content": s.content, "items": s.items}
                for s in self.sections
            ],
            "summary": self.summary,
        }


class ReportGenerator:
    """Gerador de relatórios de grid."""

    def __init__(self) -> None:
        self.reports: list[GridReport] = []

    def generate_compliance_report(
        self,
        site_id: str,
        period_start: str,
        period_end: str,
        standard: GridStandard,
        compliance_checks: list[dict],
        score: float,
    ) -> GridReport:
        """Gera relatório de compliance."""
        report = GridReport(
            site_id=site_id,
            period_start=period_start,
            period_end=period_end,
            standard=standard,
        )

        compliant = sum(
            1 for c in compliance_checks if c.get("status") == "compliant"
        )
        non_compliant = sum(
            1 for c in compliance_checks if c.get("status") == "non_compliant"
        )

        section = ReportSection(
            title="Resumo de Compliance",
            content=f"Score: {score:.1f}%",
            items=compliance_checks,
        )
        report.sections.append(section)

        if non_compliant > 0:
            recommendations = []
            for c in compliance_checks:
                if c.get("status") == "non_compliant":
                    recommendations.append(c.get("message", ""))
            rec_section = ReportSection(
                title="Recomendacoes",
                content=f"{len(recommendations)} recomendacoes",
                items=[{"recommendation": r} for r in recommendations],
            )
            report.sections.append(rec_section)

        report.summary = {
            "total_checks": len(compliance_checks),
            "compliant": compliant,
            "non_compliant": non_compliant,
            "score": score,
        }

        self.reports.append(report)
        logger.info(
            "report.generated",
            report_id=report.id,
            score=score,
        )
        return report

    def generate_quality_report(
        self,
        site_id: str,
        period_start: str,
        period_end: str,
        measurements: list[dict],
    ) -> GridReport:
        """Gera relatório de qualidade de energia."""
        report = GridReport(
            site_id=site_id,
            period_start=period_start,
            period_end=period_end,
            standard=GridStandard.PRODIST,
        )

        section = ReportSection(
            title="Qualidade de Energia",
            content=f"{len(measurements)} medições",
            items=measurements,
        )
        report.sections.append(section)

        non_compliant = sum(
            1 for m in measurements if m.get("compliance") == "non_compliant"
        )
        report.summary = {
            "total_measurements": len(measurements),
            "non_compliant": non_compliant,
        }

        self.reports.append(report)
        return report

    def generate_fault_report(
        self,
        site_id: str,
        period_start: str,
        period_end: str,
        events: list[dict],
    ) -> GridReport:
        """Gera relatório de eventos de falha."""
        report = GridReport(
            site_id=site_id,
            period_start=period_start,
            period_end=period_end,
            standard=GridStandard.PRODIST,
        )

        section = ReportSection(
            title="Eventos de Falha",
            content=f"{len(events)} eventos",
            items=events,
        )
        report.sections.append(section)

        non_compliant = sum(
            1 for e in events if e.get("compliance") == "non_compliant"
        )
        report.summary = {
            "total_events": len(events),
            "non_compliant": non_compliant,
        }

        self.reports.append(report)
        return report

    def get_report(self, report_id: str) -> GridReport | None:
        """Busca relatório por ID."""
        for r in self.reports:
            if r.id == report_id:
                return r
        return None

    def get_reports_by_site(self, site_id: str) -> list[GridReport]:
        """Retorna relatórios por site."""
        return [r for r in self.reports if r.site_id == site_id]

    def get_reports_by_period(
        self, start: str, end: str
    ) -> list[GridReport]:
        """Retorna relatórios por período."""
        return [
            r
            for r in self.reports
            if r.period_start >= start and r.period_end <= end
        ]

    def delete_report(self, report_id: str) -> bool:
        """Deleta um relatório."""
        for i, r in enumerate(self.reports):
            if r.id == report_id:
                del self.reports[i]
                return True
        return False

    def get_statistics(self) -> dict:
        """Retorna estatísticas de relatórios."""
        return {
            "total_reports": len(self.reports),
            "by_site": {},
        }

    def clear(self) -> int:
        """Limpa todos os relatórios."""
        count = len(self.reports)
        self.reports.clear()
        return count
