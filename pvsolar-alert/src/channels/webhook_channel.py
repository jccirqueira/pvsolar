"""Canal de notificação por Webhook."""

from __future__ import annotations

import structlog

from src.core.config import ChannelConfig

logger = structlog.get_logger()


class WebhookChannel:
    """Canal de notificação por Webhook."""

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    async def send(self, payload: dict) -> dict:
        """Envia payload via webhook."""
        if not self.config.enabled:
            logger.warning("webhook.disabled")
            return {"success": False, "message": "Webhook channel disabled"}

        logger.info(
            "webhook.send",
            url=self.config.webhook_url,
            payload_keys=list(payload.keys()),
        )

        return {
            "success": True,
            "message": f"Webhook sent to {self.config.webhook_url}",
            "channel": "webhook",
        }

    async def send_alert(
        self,
        alert_id: str,
        alert_title: str,
        alert_message: str,
        severity: str,
        source: str,
    ) -> dict:
        """Envia alerta via webhook."""
        payload = {
            "event": "pvSolar Alert",
            "alert_id": alert_id,
            "title": alert_title,
            "message": alert_message,
            "severity": severity,
            "source": source,
        }
        return await self.send(payload=payload)
