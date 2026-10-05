"""Engine de compliance grid code (PRODIST/ANEEL)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from src.core.config import (
    ComplianceReport,
    ComplianceStatus,
    GridStandard,
    PRODISTLimits,
)

logger = structlog.get_logger()


@dataclass
class ComplianceCheck:
    """Resultado de uma verificação de compliance."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: ComplianceStatus = ComplianceStatus.UNKNOWN
    actual_value: float = 0.0
    limit_value: float = 0.0
    unit: str = ""
    message: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Converte para dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "actual_value": self.actual_value,
            "limit_value": self.limit_value,
            "unit": self.unit,
            "message": self.message,
            "checked_at": self.checked_at.isoformat(),
        }


class ComplianceEngine:
    """Engine de verificação de compliance."""

    def __init__(self, limits: PRODISTLimits | None = None) -> None:
        self.limits = limits or PRODISTLimits()
        self.checks: list[ComplianceCheck] = []
        self.reports: list[ComplianceReport] = []

    def check_voltage(self, voltage_pu: float) -> ComplianceCheck:
        """Verifica tensão conforme PRODIST."""
        if voltage_pu < self.limits.voltage_min_pu:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"Tensão {voltage_pu:.3f} p.u. abaixo do mínimo {self.limits.voltage_min_pu}"
        elif voltage_pu > self.limits.voltage_max_pu:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"Tensão {voltage_pu:.3f} p.u. acima do máximo {self.limits.voltage_max_pu}"
        else:
            status = ComplianceStatus.COMPLIANT
            msg = f"Tensão {voltage_pu:.3f} p.u. dentro dos limites"

        check = ComplianceCheck(
            name="Tensão PCC",
            description="Verificação de tensão no Ponto de Conexão comum",
            status=status,
            actual_value=voltage_pu,
            limit_value=self.limits.voltage_max_pu,
            unit="p.u.",
            message=msg,
        )
        self.checks.append(check)
        logger.info("compliance.voltage", status=status.value, value=voltage_pu)
        return check

    def check_thd_voltage(self, thd_percent: float) -> ComplianceCheck:
        """Verifica THD de tensão conforme PRODIST."""
        if thd_percent > self.limits.thd_v_max:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"THD {thd_percent:.2f}% acima do máximo {self.limits.thd_v_max}%"
        else:
            status = ComplianceStatus.COMPLIANT
            msg = f"THD {thd_percent:.2f}% dentro do limite"

        check = ComplianceCheck(
            name="THD Tensão",
            description="Distorção Harmônica Total de Tensão",
            status=status,
            actual_value=thd_percent,
            limit_value=self.limits.thd_v_max,
            unit="%",
            message=msg,
        )
        self.checks.append(check)
        return check

    def check_thd_current(self, thd_percent: float) -> ComplianceCheck:
        """Verifica THD de corrente conforme PRODIST."""
        if thd_percent > self.limits.thd_i_max:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"THD {thd_percent:.2f}% acima do máximo {self.limits.thd_i_max}%"
        else:
            status = ComplianceStatus.COMPLIANT
            msg = f"THD {thd_percent:.2f}% dentro do limite"

        check = ComplianceCheck(
            name="THD Corrente",
            description="Distorção Harmônica Total de Corrente",
            status=status,
            actual_value=thd_percent,
            limit_value=self.limits.thd_i_max,
            unit="%",
            message=msg,
        )
        self.checks.append(check)
        return check

    def check_power_factor(self, pf: float) -> ComplianceCheck:
        """Verifica fator de potência conforme PRODIST."""
        if pf < self.limits.power_factor_min:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"FP {pf:.3f} abaixo do mínimo {self.limits.power_factor_min}"
        else:
            status = ComplianceStatus.COMPLIANT
            msg = f"FP {pf:.3f} dentro do limite"

        check = ComplianceCheck(
            name="Fator de Potência",
            description="Fator de Potência no Ponto de Conexão",
            status=status,
            actual_value=pf,
            limit_value=self.limits.power_factor_min,
            unit="",
            message=msg,
        )
        self.checks.append(check)
        return check

    def check_frequency(self, freq_hz: float) -> ComplianceCheck:
        """Verifica frequência conforme PRODIST."""
        if freq_hz < self.limits.frequency_min:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"Frequência {freq_hz:.2f} Hz abaixo do mínimo"
        elif freq_hz > self.limits.frequency_max:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"Frequência {freq_hz:.2f} Hz acima do máximo"
        else:
            status = ComplianceStatus.COMPLIANT
            msg = f"Frequência {freq_hz:.2f} Hz dentro dos limites"

        check = ComplianceCheck(
            name="Frequência",
            description="Frequência do Sistema",
            status=status,
            actual_value=freq_hz,
            limit_value=self.limits.frequency_max,
            unit="Hz",
            message=msg,
        )
        self.checks.append(check)
        return check

    def check_flicker(self, pst: float) -> ComplianceCheck:
        """Verifica flicker conforme PRODIST."""
        if pst > self.limits.flicker_pst_max:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"Flicker PST {pst:.3f} acima do máximo"
        else:
            status = ComplianceStatus.COMPLIANT
            msg = f"Flicker PST {pst:.3f} dentro do limite"

        check = ComplianceCheck(
            name="Flicker",
            description="Short-term flicker indicator (Pst)",
            status=status,
            actual_value=pst,
            limit_value=self.limits.flicker_pst_max,
            unit="Pst",
            message=msg,
        )
        self.checks.append(check)
        return check

    def check_unbalance(self, unbalance_percent: float) -> ComplianceCheck:
        """Verifica desquilíbrio conforme PRODIST."""
        if unbalance_percent > self.limits.unbalance_max:
            status = ComplianceStatus.NON_COMPLIANT
            msg = f"Desequilíbrio {unbalance_percent:.2f}% acima do máximo"
        else:
            status = ComplianceStatus.COMPLIANT
            msg = f"Desequilíbrio {unbalance_percent:.2f}% dentro do limite"

        check = ComplianceCheck(
            name="Desequilíbrio",
            description="Desequilíbrio de Tensão",
            status=status,
            actual_value=unbalance_percent,
            limit_value=self.limits.unbalance_max,
            unit="%",
            message=msg,
        )
        self.checks.append(check)
        return check

    def run_full_check(self, measurements: dict) -> list[ComplianceCheck]:
        """Executa verificação completa."""
        checks = []

        if "voltage_pu" in measurements:
            checks.append(self.check_voltage(measurements["voltage_pu"]))
        if "thd_v" in measurements:
            checks.append(self.check_thd_voltage(measurements["thd_v"]))
        if "thd_i" in measurements:
            checks.append(self.check_thd_current(measurements["thd_i"]))
        if "power_factor" in measurements:
            checks.append(self.check_power_factor(measurements["power_factor"]))
        if "frequency" in measurements:
            checks.append(self.check_frequency(measurements["frequency"]))
        if "flicker" in measurements:
            checks.append(self.check_flicker(measurements["flicker"]))
        if "unbalance" in measurements:
            checks.append(self.check_unbalance(measurements["unbalance"]))

        return checks

    def get_overall_status(self) -> ComplianceStatus:
        """Retorna status geral de compliance."""
        if not self.checks:
            return ComplianceStatus.UNKNOWN

        statuses = [c.status for c in self.checks]
        if ComplianceStatus.NON_COMPLIANT in statuses:
            return ComplianceStatus.NON_COMPLIANT
        if ComplianceStatus.WARNING in statuses:
            return ComplianceStatus.WARNING
        if all(s == ComplianceStatus.COMPLIANT for s in statuses):
            return ComplianceStatus.COMPLIANT
        return ComplianceStatus.UNKNOWN

    def get_score(self) -> float:
        """Retorna score de compliance (0-100)."""
        if not self.checks:
            return 0.0

        total = len(self.checks)
        compliant = sum(
            1 for c in self.checks if c.status == ComplianceStatus.COMPLIANT
        )
        return (compliant / total) * 100.0

    def generate_report(
        self, period_start: str, period_end: str, standard: GridStandard
    ) -> ComplianceReport:
        """Gera relatório de compliance."""
        report = ComplianceReport(
            id=str(uuid.uuid4()),
            period_start=period_start,
            period_end=period_end,
            standard=standard,
            overall_status=self.get_overall_status(),
            checks=[c.to_dict() for c in self.checks],
            score=self.get_score(),
            recommendations=self._generate_recommendations(),
        )
        self.reports.append(report)
        logger.info(
            "compliance.report_generated",
            report_id=report.id,
            score=report.score,
        )
        return report

    def _generate_recommendations(self) -> list[str]:
        """Gera recomendações baseadas nos checks."""
        recommendations = []
        non_compliant = [
            c for c in self.checks if c.status == ComplianceStatus.NON_COMPLIANT
        ]
        for check in non_compliant:
            if "Tensão" in check.name:
                recommendations.append(
                    f"Ajustar tensão: {check.message}"
                )
            elif "THD" in check.name:
                recommendations.append(
                    f"Instalar filtros harmônicos: {check.message}"
                )
            elif "Fator" in check.name:
                recommendations.append(
                    f"Corrigir fator de potência: {check.message}"
                )
            elif "Frequência" in check.name:
                recommendations.append(
                    f"Verificar controle de frequência: {check.message}"
                )
        return recommendations

    def get_check_history(self, name: str | None = None) -> list[ComplianceCheck]:
        """Retorna histórico de checks."""
        if name:
            return [c for c in self.checks if c.name == name]
        return list(self.checks)

    def get_statistics(self) -> dict:
        """Retorna estatísticas de compliance."""
        total = len(self.checks)
        by_status = {}
        for s in ComplianceStatus:
            by_status[s.value] = sum(
                1 for c in self.checks if c.status == s
            )
        return {
            "total_checks": total,
            "overall_status": self.get_overall_status().value,
            "score": self.get_score(),
            "by_status": by_status,
            "reports_generated": len(self.reports),
        }

    def clear(self) -> int:
        """Limpa todos os checks."""
        count = len(self.checks)
        self.checks.clear()
        return count
