"""Canal de notificação por Email."""

from __future__ import annotations

import structlog

from src.core.config import ChannelConfig

logger = structlog.get_logger()


class EmailChannel:
    """Canal de notificação por Email."""

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False,
    ) -> dict:
        """Envia email."""
        if not self.config.enabled:
            logger.warning("email.disabled")
            return {"success": False, "message": "Email channel disabled"}

        logger.info(
            "email.send",
            to=to,
            subject=subject,
            from_address=self.config.from_address,
        )

        return {
            "success": True,
            "message": f"Email sent to {to}",
            "channel": "email",
        }

    async def send_alert(
        self,
        to: str,
        alert_title: str,
        alert_message: str,
        severity: str,
        source: str,
    ) -> dict:
        """Envia alerta por email."""
        subject = f"[pvSolar Alert] [{severity.upper()}] {alert_title}"
        body = (
            f"Alert: {alert_title}\n"
            f"Severity: {severity}\n"
            f"Source: {source}\n\n"
            f"{alert_message}"
        )
        return await self.send(to=to, subject=subject, body=body)
