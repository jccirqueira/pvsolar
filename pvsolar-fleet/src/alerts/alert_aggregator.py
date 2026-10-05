"""
Alert Aggregator Module.

Centralizes and manages alerts across all sites.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from src.core.config import AlertSeverity, AlertStatus

logger = structlog.get_logger(__name__)


class FleetAlert:
    """Represents a fleet-wide alert."""

    def __init__(
        self,
        alert_id: str,
        site_id: str,
        site_name: str,
        severity: AlertSeverity,
        message: str,
        source: str = "",
    ):
        self.alert_id = alert_id
        self.site_id = site_id
        self.site_name = site_name
        self.severity = severity
        self.message = message
        self.source = source
        self.status: AlertStatus = AlertStatus.ACTIVE
        self.created_at: datetime = datetime.now(UTC)
        self.acknowledged_at: datetime | None = None
        self.acknowledged_by: str | None = None
        self.resolved_at: datetime | None = None
        self.escalation_level: int = 0
        self.tags: list[str] = []
        self.context: dict[str, Any] = {}

    def acknowledge(self, user: str = "system") -> None:
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(UTC)
        self.acknowledged_by = user

    def resolve(self) -> None:
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)

    def escalate(self) -> None:
        self.escalation_level += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "site_id": self.site_id,
            "site_name": self.site_name,
            "severity": self.severity.value,
            "message": self.message,
            "source": self.source,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "escalation_level": self.escalation_level,
            "tags": self.tags,
            "context": self.context,
        }


class AlertAggregator:
    """
    Aggregates alerts from all sites.

    Features:
    - Centralized alert management
    - Escalation rules
    - Filtering and search
    - Statistics
    """

    def __init__(self, max_alerts: int = 1000):
        self._alerts: list[FleetAlert] = []
        self._max_alerts = max_alerts
        self._callbacks: list[Callable] = []

    def add_alert(self, alert: FleetAlert) -> None:
        self._alerts.insert(0, alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[:self._max_alerts]
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error("alert.callback_error", error=str(e))
        logger.info(
            "alert.added",
            alert_id=alert.alert_id,
            site=alert.site_name,
            severity=alert.severity.value,
        )

    def create_alert(
        self,
        site_id: str,
        site_name: str,
        severity: AlertSeverity,
        message: str,
        source: str = "",
        **kwargs: Any,
    ) -> FleetAlert:
        import uuid
        alert_id = f"alert_{str(uuid.uuid4())[:8]}"
        alert = FleetAlert(alert_id, site_id, site_name, severity, message, source)
        for key, value in kwargs.items():
            if key == "tags" and isinstance(value, list):
                alert.tags = value
            elif key == "context" and isinstance(value, dict):
                alert.context = value
        self.add_alert(alert)
        return alert

    def acknowledge_alert(self, alert_id: str, user: str = "operator") -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledge(user)
                logger.info("alert.acknowledged", alert_id=alert_id, user=user)
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolve()
                logger.info("alert.resolved", alert_id=alert_id)
                return True
        return False

    def acknowledge_all(self, user: str = "operator") -> int:
        count = 0
        for alert in self._alerts:
            if alert.status == AlertStatus.ACTIVE:
                alert.acknowledge(user)
                count += 1
        return count

    def get_alerts(
        self,
        site_id: str | None = None,
        severity: AlertSeverity | None = None,
        status: AlertStatus | None = None,
        limit: int = 100,
    ) -> list[FleetAlert]:
        results = self._alerts
        if site_id:
            results = [a for a in results if a.site_id == site_id]
        if severity:
            results = [a for a in results if a.severity == severity]
        if status:
            results = [a for a in results if a.status == status]
        return results[:limit]

    def get_active_alerts(self) -> list[FleetAlert]:
        return self.get_alerts(status=AlertStatus.ACTIVE)

    def get_critical_alerts(self) -> list[FleetAlert]:
        return self.get_alerts(severity=AlertSeverity.CRITICAL, status=AlertStatus.ACTIVE)

    def get_site_alerts(self, site_id: str) -> list[FleetAlert]:
        return self.get_alerts(site_id=site_id)

    def get_statistics(self) -> dict[str, Any]:
        active = self.get_active_alerts()
        return {
            "total_alerts": len(self._alerts),
            "active": len(active),
            "critical": len([a for a in active if a.severity == AlertSeverity.CRITICAL]),
            "warning": len([a for a in active if a.severity == AlertSeverity.WARNING]),
            "info": len([a for a in active if a.severity == AlertSeverity.INFO]),
            "acknowledged": len([a for a in self._alerts if a.status == AlertStatus.ACKNOWLEDGED]),
            "resolved": len([a for a in self._alerts if a.status == AlertStatus.RESOLVED]),
        }

    def get_site_statistics(self, site_id: str) -> dict[str, Any]:
        site_alerts = self.get_site_alerts(site_id)
        active = [a for a in site_alerts if a.status == AlertStatus.ACTIVE]
        return {
            "site_id": site_id,
            "total": len(site_alerts),
            "active": len(active),
            "critical": len([a for a in active if a.severity == AlertSeverity.CRITICAL]),
            "warning": len([a for a in active if a.severity == AlertSeverity.WARNING]),
            "info": len([a for a in active if a.severity == AlertSeverity.INFO]),
        }

    def register_callback(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alerts": [a.to_dict() for a in self._alerts[:100]],
            "statistics": self.get_statistics(),
        }
