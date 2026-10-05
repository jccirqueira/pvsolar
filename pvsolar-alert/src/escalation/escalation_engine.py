"""Engine de escalation de alertas."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from src.core.config import (
    AlertSeverity,
    EscalationLevel,
    EscalationRuleConfig,
    NotificationChannel,
)
from src.core.notification_manager import Alert

logger = structlog.get_logger()

SEVERITY_ESCALATION_ORDER = [
    AlertSeverity.INFO,
    AlertSeverity.LOW,
    AlertSeverity.MEDIUM,
    AlertSeverity.HIGH,
    AlertSeverity.CRITICAL,
]

LEVEL_ORDER = [
    EscalationLevel.LEVEL_1,
    EscalationLevel.LEVEL_2,
    EscalationLevel.LEVEL_3,
    EscalationLevel.LEVEL_4,
]


def get_escalation_level_for_severity(
    severity: AlertSeverity,
) -> EscalationLevel:
    """Retorna nível de escalation baseado na severidade."""
    severity_map = {
        AlertSeverity.INFO: EscalationLevel.LEVEL_1,
        AlertSeverity.LOW: EscalationLevel.LEVEL_1,
        AlertSeverity.MEDIUM: EscalationLevel.LEVEL_2,
        AlertSeverity.HIGH: EscalationLevel.LEVEL_3,
        AlertSeverity.CRITICAL: EscalationLevel.LEVEL_4,
    }
    return severity_map.get(severity, EscalationLevel.LEVEL_1)


def get_next_level(current: EscalationLevel) -> EscalationLevel | None:
    """Retorna próximo nível de escalation."""
    try:
        idx = LEVEL_ORDER.index(current)
        if idx + 1 < len(LEVEL_ORDER):
            return LEVEL_ORDER[idx + 1]
    except ValueError:
        pass
    return None


@dataclass
class EscalationManager:
    """Gerencia escalation de alertas."""

    escalation_rules: list[EscalationRuleConfig] = field(default_factory=list)
    alert_escalation_state: dict[str, dict] = field(default_factory=dict)

    def get_rule_for_level(
        self, level: EscalationLevel
    ) -> EscalationRuleConfig | None:
        """Retorna regra de escalation para um nível."""
        for rule in self.escalation_rules:
            if rule.level == level:
                return rule
        return None

    def init_escalation(self, alert: Alert) -> None:
        """Inicializa estado de escalation para um alerta."""
        initial_level = get_escalation_level_for_severity(alert.severity)
        self.alert_escalation_state[alert.id] = {
            "current_level": initial_level,
            "escalation_count": 0,
        }
        logger.info(
            "escalation.initialized",
            alert_id=alert.id,
            level=initial_level.value,
        )

    def get_current_level(self, alert_id: str) -> EscalationLevel:
        """Retorna nível atual de escalation."""
        state = self.alert_escalation_state.get(alert_id)
        if state is None:
            return EscalationLevel.LEVEL_1
        return state["current_level"]

    def should_escalate(self, alert_id: str) -> bool:
        """Verifica se o alerta deve ser escalated."""
        state = self.alert_escalation_state.get(alert_id)
        if state is None:
            return False
        current = state["current_level"]
        return get_next_level(current) is not None

    def escalate(self, alert_id: str) -> EscalationLevel | None:
        """Escalation do alerta para o próximo nível."""
        state = self.alert_escalation_state.get(alert_id)
        if state is None:
            return None

        current = state["current_level"]
        next_level = get_next_level(current)
        if next_level is None:
            return None

        state["current_level"] = next_level
        state["escalation_count"] += 1
        logger.info(
            "escalation.escalated",
            alert_id=alert_id,
            from_level=current.value,
            to_level=next_level.value,
        )
        return next_level

    def get_escalation_contacts(
        self, level: EscalationLevel
    ) -> list[dict]:
        """Retorna contatos para um nível de escalation."""
        rule = self.get_rule_for_level(level)
        if rule is None:
            return []
        contacts = []
        for c in rule.contacts:
            contacts.append(
                {
                    "name": c.name,
                    "email": c.email,
                    "phone": c.phone,
                    "telegram_chat_id": c.telegram_chat_id,
                    "whatsapp_number": c.whatsapp_number,
                    "channels": [ch.value for ch in c.channels],
                }
            )
        return contacts

    def get_escalation_channels(
        self, level: EscalationLevel
    ) -> list[NotificationChannel]:
        """Retorna canais para um nível de escalation."""
        rule = self.get_rule_for_level(level)
        if rule is None:
            return []
        all_channels: set[NotificationChannel] = set()
        for c in rule.contacts:
            all_channels.update(c.channels)
        return list(all_channels)

    def get_escalation_wait_seconds(self, level: EscalationLevel) -> int:
        """Retorna tempo de espera para um nível."""
        rule = self.get_rule_for_level(level)
        if rule is None:
            return 300
        return rule.wait_seconds

    def get_escalation_stats(self) -> dict:
        """Retorna estatísticas de escalation."""
        total = len(self.alert_escalation_state)
        by_level = {}
        for level in LEVEL_ORDER:
            by_level[level.value] = sum(
                1
                for s in self.alert_escalation_state.values()
                if s["current_level"] == level
            )
        return {
            "total_escalated": total,
            "by_level": by_level,
        }

    def reset_escalation(self, alert_id: str) -> bool:
        """Reseta escalation de um alerta."""
        if alert_id in self.alert_escalation_state:
            del self.alert_escalation_state[alert_id]
            logger.info("escalation.reset", alert_id=alert_id)
            return True
        return False

    def clear_all(self) -> int:
        """Limpa todos os estados de escalation."""
        count = len(self.alert_escalation_state)
        self.alert_escalation_state.clear()
        return count
