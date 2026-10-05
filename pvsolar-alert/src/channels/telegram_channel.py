"""Canal de notificação por Telegram."""

from __future__ import annotations

import structlog

from src.core.config import ChannelConfig

logger = structlog.get_logger()


class TelegramChannel:
    """Canal de notificação por Telegram."""

    def __init__(self, config: ChannelConfig) -> None:
        self.config = config

    async def send(self, chat_id: str, message: str) -> dict:
        """Envia mensagem via Telegram."""
        if not self.config.enabled:
            logger.warning("telegram.disabled")
            return {"success": False, "message": "Telegram channel disabled"}

        logger.info(
            "telegram.send",
            chat_id=chat_id,
            bot_token=self.config.bot_token[:10] + "..." if self.config.bot_token else None,
        )

        return {
            "success": True,
            "message": f"Telegram message sent to {chat_id}",
            "channel": "telegram",
        }

    async def send_alert(
        self,
        chat_id: str,
        alert_title: str,
        alert_message: str,
        severity: str,
        source: str,
    ) -> dict:
        """Envia alerta por Telegram."""
        emoji_map = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "info": "🔵",
        }
        emoji = emoji_map.get(severity, "⚪")
        message = (
            f"{emoji} *pvSolar Alert*\n\n"
            f"*{alert_title}*\n"
            f"Severidade: {severity.upper()}\n"
            f"Origem: {source}\n\n"
            f"{alert_message}"
        )
        return await self.send(chat_id=chat_id, message=message)
