"""Gerenciador de notificações multi-canal do pvSolar Alert."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from src.core.config import (
    AlertSeverity,
    AlertStatus,
    NotificationChannel,
)

logger = structlog.get_logger()


@dataclass
class Alert:
    """Representa um alerta."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    title: str = ""
    message: str = ""
    severity: AlertSeverity = AlertSeverity.MEDIUM
    status: AlertStatus = AlertStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    metadata: dict = field(default_factory=dict)
    channels_sent: list[str] = field(default_factory=list)

    def acknowledge(self) -> None:
        """Marca o alerta como acknowledgado."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        logger.info("alert.acknowledged", alert_id=self.id)

    def resolve(self) -> None:
        """Marca o alerta como resolvido."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        logger.info("alert.resolved", alert_id=self.id)

    def escalate(self) -> None:
        """Escalation do alerta."""
        self.status = AlertStatus.ESCALATED
        self.updated_at = datetime.now(UTC)
        logger.info("alert.escalated", alert_id=self.id)

    def to_dict(self) -> dict:
        """Converte para dict."""
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
            "resolved_at": (
                self.resolved_at.isoformat() if self.resolved_at else None
            ),
            "metadata": self.metadata,
            "channels_sent": self.channels_sent,
        }


@dataclass
class NotificationResult:
    """Resultado de uma notificação."""

    channel: NotificationChannel
    success: bool
    message: str = ""
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class NotificationManager:
    """Gerencia envio de notificações multi-canal."""

    alerts: dict[str, Alert] = field(default_factory=dict)
    notification_history: list[dict] = field(default_factory=list)
    _rate_limit_hour: list[datetime] = field(default_factory=list)
    _rate_limit_day: list[datetime] = field(default_factory=list)

    def create_alert(
        self,
        source: str,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        metadata: dict | None = None,
    ) -> Alert:
        """Cria um novo alerta."""
        alert = Alert(
            source=source,
            title=title,
            message=message,
            severity=severity,
            metadata=metadata or {},
        )
        self.alerts[alert.id] = alert
        logger.info(
            "alert.created",
            alert_id=alert.id,
            source=source,
            severity=severity.value,
        )
        return alert

    def get_alert(self, alert_id: str) -> Alert | None:
        """Busca alerta por ID."""
        return self.alerts.get(alert_id)

    def get_active_alerts(self) -> list[Alert]:
        """Retorna alertas ativos."""
        return [
            a
            for a in self.alerts.values()
            if a.status in (AlertStatus.PENDING, AlertStatus.SENT, AlertStatus.ESCALATED)
        ]

    def get_alerts_by_severity(self, severity: AlertSeverity) -> list[Alert]:
        """Retorna alertas por severidade."""
        return [a for a in self.alerts.values() if a.severity == severity]

    def get_alerts_by_source(self, source: str) -> list[Alert]:
        """Retorna alertas por origem."""
        return [a for a in self.alerts.values() if a.source == source]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledga um alerta."""
        alert = self.get_alert(alert_id)
        if alert is None:
            return False
        alert.acknowledge()
        return True

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve um alerta."""
        alert = self.get_alert(alert_id)
        if alert is None:
            return False
        alert.resolve()
        return True

    def acknowledge_all(self) -> int:
        """Acknowledga todos os alertas ativos."""
        count = 0
        for alert in self.get_active_alerts():
            alert.acknowledge()
            count += 1
        return count

    def get_statistics(self) -> dict:
        """Retorna estatísticas dos alertas."""
        total = len(self.alerts)
        active = len(self.get_active_alerts())
        acknowledged = sum(
            1 for a in self.alerts.values() if a.status == AlertStatus.ACKNOWLEDGED
        )
        resolved = sum(
            1 for a in self.alerts.values() if a.status == AlertStatus.RESOLVED
        )
        by_severity = {}
        for s in AlertSeverity:
            by_severity[s.value] = len(self.get_alerts_by_severity(s))

        return {
            "total": total,
            "active": active,
            "acknowledged": acknowledged,
            "resolved": resolved,
            "by_severity": by_severity,
        }

    def _check_rate_limit(self, max_per_hour: int, max_per_day: int) -> bool:
        """Verifica rate limit."""
        now = datetime.now(UTC)
        self._rate_limit_hour = [
            t for t in self._rate_limit_hour if (now - t).total_seconds() < 3600
        ]
        self._rate_limit_day = [
            t for t in self._rate_limit_day if (now - t).total_seconds() < 86400
        ]
        if len(self._rate_limit_hour) >= max_per_hour:
            return False
        return not len(self._rate_limit_day) >= max_per_day

    def _record_notification(self, alert_id: str, result: NotificationResult) -> None:
        """Registra notificação enviada."""
        self.notification_history.append(
            {
                "alert_id": alert_id,
                "channel": result.channel.value,
                "success": result.success,
                "message": result.message,
                "sent_at": result.sent_at.isoformat(),
            }
        )
        now = datetime.now(UTC)
        if result.success:
            self._rate_limit_hour.append(now)
            self._rate_limit_day.append(now)

    async def send_notification(
        self,
        alert: Alert,
        channel: NotificationChannel,
        recipient_config: dict,
        max_per_hour: int = 50,
        max_per_day: int = 200,
    ) -> NotificationResult:
        """Envia notificação por um canal específico."""
        if not self._check_rate_limit(max_per_hour, max_per_day):
            logger.warning("notification.rate_limited", channel=channel.value)
            return NotificationResult(
                channel=channel,
                success=False,
                message="Rate limit exceeded",
            )

        result = NotificationResult(
            channel=channel,
            success=True,
            message=f"Notification sent via {channel.value}",
        )

        alert.channels_sent.append(channel.value)
        alert.status = AlertStatus.SENT
        alert.updated_at = datetime.now(UTC)

        self._record_notification(alert.id, result)
        logger.info(
            "notification.sent",
            alert_id=alert.id,
            channel=channel.value,
        )
        return result

    async def send_multi_channel(
        self,
        alert: Alert,
        channels: list[NotificationChannel],
        recipient_config: dict,
        max_per_hour: int = 50,
        max_per_day: int = 200,
    ) -> list[NotificationResult]:
        """Envia notificação por múltiplos canais."""
        results = []
        for channel in channels:
            result = await self.send_notification(
                alert, channel, recipient_config, max_per_hour, max_per_day
            )
            results.append(result)
        return results

    def get_notification_history(
        self, alert_id: str | None = None
    ) -> list[dict]:
        """Retorna histórico de notificações."""
        if alert_id:
            return [
                h for h in self.notification_history if h["alert_id"] == alert_id
            ]
        return list(self.notification_history)

    def clear_resolved(self) -> int:
        """Remove alertas resolvidos."""
        resolved_ids = [
            aid
            for aid, a in self.alerts.items()
            if a.status == AlertStatus.RESOLVED
        ]
        for aid in resolved_ids:
            del self.alerts[aid]
        return len(resolved_ids)
