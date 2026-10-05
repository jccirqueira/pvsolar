"""Analisador de qualidade de energia."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog

from src.core.config import (
    ComplianceStatus,
    PRODISTLimits,
    QualityMeasurement,
    QualityMetric,
)

logger = structlog.get_logger()


class QualityAnalyzer:
    """Analisador de qualidade de energia conforme PRODIST."""

    def __init__(self, limits: PRODISTLimits | None = None) -> None:
        self.limits = limits or PRODISTLimits()
        self.measurements: list[QualityMeasurement] = []

    def analyze_thd_voltage(self, thd_percent: float) -> QualityMeasurement:
        """Analisa THD de tensão."""
        compliance = (
            ComplianceStatus.COMPLIANT
            if thd_percent <= self.limits.thd_v_max
            else ComplianceStatus.NON_COMPLIANT
        )
        m = QualityMeasurement(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            metric=QualityMetric.THD_V,
            value=thd_percent,
            unit="%",
            limit=self.limits.thd_v_max,
            compliance=compliance,
        )
        self.measurements.append(m)
        logger.info("quality.thd_v", value=thd_percent, status=compliance.value)
        return m

    def analyze_thd_current(self, thd_percent: float) -> QualityMeasurement:
        """Analisa THD de corrente."""
        compliance = (
            ComplianceStatus.COMPLIANT
            if thd_percent <= self.limits.thd_i_max
            else ComplianceStatus.NON_COMPLIANT
        )
        m = QualityMeasurement(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            metric=QualityMetric.THD_I,
            value=thd_percent,
            unit="%",
            limit=self.limits.thd_i_max,
            compliance=compliance,
        )
        self.measurements.append(m)
        return m

    def analyze_voltage(self, voltage_pu: float) -> QualityMeasurement:
        """Analisa tensão no PCC."""
        if voltage_pu < self.limits.voltage_min_pu or voltage_pu > self.limits.voltage_max_pu:
            compliance = ComplianceStatus.NON_COMPLIANT
        else:
            compliance = ComplianceStatus.COMPLIANT

        m = QualityMeasurement(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            metric=QualityMetric.PCC_VOLTAGE,
            value=voltage_pu,
            unit="p.u.",
            limit=self.limits.voltage_max_pu,
            compliance=compliance,
        )
        self.measurements.append(m)
        return m

    def analyze_power_factor(self, pf: float) -> QualityMeasurement:
        """Analisa fator de potência."""
        compliance = (
            ComplianceStatus.COMPLIANT
            if pf >= self.limits.power_factor_min
            else ComplianceStatus.NON_COMPLIANT
        )
        m = QualityMeasurement(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            metric=QualityMetric.POWER_FACTOR,
            value=pf,
            unit="",
            limit=self.limits.power_factor_min,
            compliance=compliance,
        )
        self.measurements.append(m)
        return m

    def analyze_frequency(self, freq_hz: float) -> QualityMeasurement:
        """Analisa frequência."""
        if freq_hz < self.limits.frequency_min or freq_hz > self.limits.frequency_max:
            compliance = ComplianceStatus.NON_COMPLIANT
        else:
            compliance = ComplianceStatus.COMPLIANT

        m = QualityMeasurement(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            metric=QualityMetric.FREQUENCY,
            value=freq_hz,
            unit="Hz",
            limit=self.limits.frequency_max,
            compliance=compliance,
        )
        self.measurements.append(m)
        return m

    def analyze_flicker(self, pst: float) -> QualityMeasurement:
        """Analisa flicker."""
        compliance = (
            ComplianceStatus.COMPLIANT
            if pst <= self.limits.flicker_pst_max
            else ComplianceStatus.NON_COMPLIANT
        )
        m = QualityMeasurement(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            metric=QualityMetric.FLICKER,
            value=pst,
            unit="Pst",
            limit=self.limits.flicker_pst_max,
            compliance=compliance,
        )
        self.measurements.append(m)
        return m

    def analyze_unbalance(self, unbalance_percent: float) -> QualityMeasurement:
        """Analisa desquilíbrio."""
        compliance = (
            ComplianceStatus.COMPLIANT
            if unbalance_percent <= self.limits.unbalance_max
            else ComplianceStatus.NON_COMPLIANT
        )
        m = QualityMeasurement(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            metric=QualityMetric.UNBALANCE,
            value=unbalance_percent,
            unit="%",
            limit=self.limits.unbalance_max,
            compliance=compliance,
        )
        self.measurements.append(m)
        return m

    def analyze_reactive_power(
        self, q_kvar: float, max_kvar: float
    ) -> QualityMeasurement:
        """Analisa potência reativa."""
        compliance = (
            ComplianceStatus.COMPLIANT
            if abs(q_kvar) <= abs(max_kvar)
            else ComplianceStatus.NON_COMPLIANT
        )
        m = QualityMeasurement(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            metric=QualityMetric.REACTIVE_POWER,
            value=q_kvar,
            unit="kVAr",
            limit=max_kvar,
            compliance=compliance,
        )
        self.measurements.append(m)
        return m

    def analyze_all(self, data: dict) -> list[QualityMeasurement]:
        """Analisa todas as métricas disponíveis."""
        results = []
        if "thd_v" in data:
            results.append(self.analyze_thd_voltage(data["thd_v"]))
        if "thd_i" in data:
            results.append(self.analyze_thd_current(data["thd_i"]))
        if "voltage_pu" in data:
            results.append(self.analyze_voltage(data["voltage_pu"]))
        if "power_factor" in data:
            results.append(self.analyze_power_factor(data["power_factor"]))
        if "frequency" in data:
            results.append(self.analyze_frequency(data["frequency"]))
        if "flicker" in data:
            results.append(self.analyze_flicker(data["flicker"]))
        if "unbalance" in data:
            results.append(self.analyze_unbalance(data["unbalance"]))
        return results

    def get_measurements_by_metric(
        self, metric: QualityMetric
    ) -> list[QualityMeasurement]:
        """Retorna medições por métrica."""
        return [m for m in self.measurements if m.metric == metric]

    def get_non_compliant(self) -> list[QualityMeasurement]:
        """Retorna medições não conformes."""
        return [
            m
            for m in self.measurements
            if m.compliance == ComplianceStatus.NON_COMPLIANT
        ]

    def get_compliance_rate(self) -> float:
        """Retorna taxa de compliance (%)."""
        if not self.measurements:
            return 0.0
        compliant = sum(
            1
            for m in self.measurements
            if m.compliance == ComplianceStatus.COMPLIANT
        )
        return (compliant / len(self.measurements)) * 100.0

    def get_statistics(self) -> dict:
        """Retorna estatísticas de qualidade."""
        total = len(self.measurements)
        by_metric = {}
        for metric in QualityMetric:
            count = len(self.get_measurements_by_metric(metric))
            if count > 0:
                by_metric[metric.value] = count

        return {
            "total_measurements": total,
            "compliance_rate": self.get_compliance_rate(),
            "non_compliant_count": len(self.get_non_compliant()),
            "by_metric": by_metric,
        }

    def clear(self) -> int:
        """Limpa todas as medições."""
        count = len(self.measurements)
        self.measurements.clear()
        return count
