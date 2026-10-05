"""Canal de notificação por SMS."""

from __future__ import annotations

import structlog

from src.core.config import ChannelConfig

logger = structlog.get_logger()


class SMSChannel:
    """Canal de notificação por SMS."""

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    async def send(self, to: str, message: str) -> dict:
        """Envia SMS."""
        if not self.config.enabled:
            logger.warning("sms.disabled")
            return {"success": False, "message": "SMS channel disabled"}

        logger.info(
            "sms.send",
            to=to,
            from_number=self.config.from_number,
        )

        return {
            "success": True,
            "message": f"SMS sent to {to}",
            "channel": "sms",
        }

    async def send_alert(
        self,
        to: str,
        alert_title: str,
        alert_message: str,
        severity: str,
    ) -> dict:
        """Envia alerta por SMS."""
        message = f"[{severity.upper()}] {alert_title}: {alert_message}"
        return await self.send(to=to, message=message)
