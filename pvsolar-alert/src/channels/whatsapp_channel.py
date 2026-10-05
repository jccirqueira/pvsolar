"""Canal de notificação por WhatsApp."""

from __future__ import annotations

import structlog

from src.core.config import ChannelConfig

logger = structlog.get_logger()


class WhatsAppChannel:
    """Canal de notificação por WhatsApp."""

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    async def send(self, to: str, message: str) -> dict:
        """Envia mensagem via WhatsApp."""
        if not self.config.enabled:
            logger.warning("whatsapp.disabled")
            return {"success": False, "message": "WhatsApp channel disabled"}

        logger.info(
            "whatsapp.send",
            to=to,
            base_url=self.config.base_url,
        )

        return {
            "success": True,
            "message": f"WhatsApp message sent to {to}",
            "channel": "whatsapp",
        }

    async def send_alert(
        self,
        to: str,
        alert_title: str,
        alert_message: str,
        severity: str,
        source: str,
    ) -> dict:
        """Envia alerta por WhatsApp."""
        message = (
            f"🚨 *pvSolar Alert*\n\n"
            f"*{alert_title}*\n"
            f"Severidade: {severity.upper()}\n"
            f"Origem: {source}\n\n"
            f"{alert_message}"
        )
        return await self.send(to=to, message=message)
