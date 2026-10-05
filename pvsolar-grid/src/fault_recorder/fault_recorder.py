"""Gravador de eventos de falha (FRT/LVRT/HVRT)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from src.core.config import (
    ComplianceStatus,
    EventRecord,
    FaultType,
    FRTConfig,
    HVRTCurve,
    LVRTCurve,
)

logger = structlog.get_logger()


class FaultRecorder:
    """Gravador de eventos de falha de grid."""

    def __init__(self, config: FRTConfig | None = None) -> None:
        self.config = config or FRTConfig()
        self.events: list[EventRecord] = []

    def _interpolate_lvrt_curve(self, time_ms: float) -> float:
        """Interpola curva LVRT para tempo dado."""
        if not self.config.lvrt_curve:
            return 0.0
        sorted_curve = sorted(self.config.lvrt_curve, key=lambda c: c.time_ms)
        if time_ms <= sorted_curve[0].time_ms:
            return sorted_curve[0].voltage_pu
        if time_ms >= sorted_curve[-1].time_ms:
            return sorted_curve[-1].voltage_pu
        for i in range(len(sorted_curve) - 1):
            t1, v1 = sorted_curve[i].time_ms, sorted_curve[i].voltage_pu
            t2, v2 = sorted_curve[i + 1].time_ms, sorted_curve[i + 1].voltage_pu
            if t1 <= time_ms <= t2:
                ratio = (time_ms - t1) / (t2 - t1) if t2 != t1 else 0
                return v1 + ratio * (v2 - v1)
        return 0.0

    def _interpolate_hvrt_curve(self, time_ms: float) -> float:
        """Interpola curva HVRT para tempo dado."""
        if not self.config.hvrt_curve:
            return 2.0
        sorted_curve = sorted(self.config.hvrt_curve, key=lambda c: c.time_ms)
        if time_ms <= sorted_curve[0].time_ms:
            return sorted_curve[0].voltage_pu
        if time_ms >= sorted_curve[-1].time_ms:
            return sorted_curve[-1].voltage_pu
        for i in range(len(sorted_curve) - 1):
            t1, v1 = sorted_curve[i].time_ms, sorted_curve[i].voltage_pu
            t2, v2 = sorted_curve[i + 1].time_ms, sorted_curve[i + 1].voltage_pu
            if t1 <= time_ms <= t2:
                ratio = (time_ms - t1) / (t2 - t1) if t2 != t1 else 0
                return v1 + ratio * (v2 - v1)
        return 2.0

    def check_lvrt_compliance(
        self, voltage_pu: float, duration_ms: float
    ) -> ComplianceStatus:
        """Verifica conformidade LVRT."""
        if not self.config.enabled:
            return ComplianceStatus.UNKNOWN
        allowed_voltage = self._interpolate_lvrt_curve(duration_ms)
        if voltage_pu >= allowed_voltage:
            return ComplianceStatus.COMPLIANT
        return ComplianceStatus.NON_COMPLIANT

    def check_hvrt_compliance(
        self, voltage_pu: float, duration_ms: float
    ) -> ComplianceStatus:
        """Verifica conformidade HVRT."""
        if not self.config.enabled:
            return ComplianceStatus.UNKNOWN
        allowed_voltage = self._interpolate_hvrt_curve(duration_ms)
        if voltage_pu <= allowed_voltage:
            return ComplianceStatus.COMPLIANT
        return ComplianceStatus.NON_COMPLIANT

    def record_event(
        self,
        event_type: FaultType,
        duration_ms: float,
        voltage_pu: float,
        frequency_hz: float = 60.0,
        details: dict | None = None,
    ) -> EventRecord:
        """Registra um evento de falha."""
        if event_type == FaultType.LVRT:
            compliance = self.check_lvrt_compliance(voltage_pu, duration_ms)
        elif event_type == FaultType.HVRT:
            compliance = self.check_hvrt_compliance(voltage_pu, duration_ms)
        else:
            compliance = ComplianceStatus.UNKNOWN

        event = EventRecord(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            duration_ms=duration_ms,
            voltage_pu=voltage_pu,
            frequency_hz=frequency_hz,
            compliance=compliance,
            details=details or {},
        )
        self.events.append(event)
        logger.info(
            "fault.event_recorded",
            event_id=event.id,
            type=event_type.value,
            compliance=compliance.value,
        )
        return event

    def get_events_by_type(self, event_type: FaultType) -> list[EventRecord]:
        """Retorna eventos por tipo."""
        return [e for e in self.events if e.event_type == event_type]

    def get_non_compliant_events(self) -> list[EventRecord]:
        """Retorna eventos não conformes."""
        return [
            e for e in self.events if e.compliance == ComplianceStatus.NON_COMPLIANT
        ]

    def get_event(self, event_id: str) -> EventRecord | None:
        """Busca evento por ID."""
        for e in self.events:
            if e.id == event_id:
                return e
        return None

    def delete_event(self, event_id: str) -> bool:
        """Deleta um evento."""
        for i, e in enumerate(self.events):
            if e.id == event_id:
                del self.events[i]
                return True
        return False

    def get_statistics(self) -> dict:
        """Retorna estatísticas de eventos."""
        total = len(self.events)
        by_type = {}
        for ft in FaultType:
            count = len(self.get_events_by_type(ft))
            if count > 0:
                by_type[ft.value] = count
        non_compliant = len(self.get_non_compliant_events())
        return {
            "total_events": total,
            "non_compliant": non_compliant,
            "compliance_rate": (
                ((total - non_compliant) / total * 100.0) if total > 0 else 0.0
            ),
            "by_type": by_type,
        }

    def clear(self) -> int:
        """Limpa todos os eventos."""
        count = len(self.events)
        self.events.clear()
        return count
