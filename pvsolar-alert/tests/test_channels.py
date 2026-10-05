"""Testes dos channels do pvSolar Alert."""

import pytest
from src.channels.email_channel import EmailChannel
from src.channels.sms_channel import SMSChannel
from src.channels.telegram_channel import TelegramChannel
from src.channels.webhook_channel import WebhookChannel
from src.channels.whatsapp_channel import WhatsAppChannel
from src.core.config import ChannelConfig

# ---------------------------------------------------------------------------
# EmailChannel
# ---------------------------------------------------------------------------

class TestEmailChannel:
    def test_create_channel(self):
        c = EmailChannel(ChannelConfig(enabled=True, api_key="k"))
        assert c.config.enabled is True

    def test_send_disabled(self):
        c = EmailChannel(ChannelConfig(enabled=False))
        import asyncio
        result = asyncio.run(c.send("a@b.com", "Sub", "Body"))
        assert result["success"] is False

    def test_send_enabled(self):
        c = EmailChannel(ChannelConfig(enabled=True, from_address="n@n.com"))
        import asyncio
        result = asyncio.run(c.send("a@b.com", "Sub", "Body"))
        assert result["success"] is True

    def test_send_alert(self):
        c = EmailChannel(ChannelConfig(enabled=True, from_address="n@n.com"))
        import asyncio
        result = asyncio.run(
            c.send_alert("a@b.com", "Overheat", "High temp", "critical", "inv1")
        )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# SMSChannel
# ---------------------------------------------------------------------------

class TestSMSChannel:
    def test_create_channel(self):
        c = SMSChannel(ChannelConfig(enabled=True))
        assert c.config.enabled is True

    def test_send_disabled(self):
        c = SMSChannel(ChannelConfig(enabled=False))
        import asyncio
        result = asyncio.run(c.send("+551199999", "msg"))
        assert result["success"] is False

    def test_send_enabled(self):
        c = SMSChannel(ChannelConfig(enabled=True, from_number="+55110000"))
        import asyncio
        result = asyncio.run(c.send("+551199999", "msg"))
        assert result["success"] is True

    def test_send_alert(self):
        c = SMSChannel(ChannelConfig(enabled=True, from_number="+55110000"))
        import asyncio
        result = asyncio.run(
            c.send_alert("+551199999", "Alert", "msg", "high")
        )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# TelegramChannel
# ---------------------------------------------------------------------------

class TestTelegramChannel:
    def test_create_channel(self):
        c = TelegramChannel(ChannelConfig(enabled=True, bot_token="token123"))
        assert c.config.bot_token == "token123"

    def test_send_disabled(self):
        c = TelegramChannel(ChannelConfig(enabled=False))
        import asyncio
        result = asyncio.run(c.send("12345", "msg"))
        assert result["success"] is False

    def test_send_enabled(self):
        c = TelegramChannel(ChannelConfig(enabled=True, bot_token="tok"))
        import asyncio
        result = asyncio.run(c.send("12345", "msg"))
        assert result["success"] is True

    def test_send_alert(self):
        c = TelegramChannel(ChannelConfig(enabled=True, bot_token="tok"))
        import asyncio
        result = asyncio.run(
            c.send_alert("12345", "Alert", "msg", "critical", "inv1")
        )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# WhatsAppChannel
# ---------------------------------------------------------------------------

class TestWhatsAppChannel:
    def test_create_channel(self):
        c = WhatsAppChannel(ChannelConfig(enabled=True, base_url="https://api.whatsapp.com"))
        assert c.config.base_url == "https://api.whatsapp.com"

    def test_send_disabled(self):
        c = WhatsAppChannel(ChannelConfig(enabled=False))
        import asyncio
        result = asyncio.run(c.send("+551199999", "msg"))
        assert result["success"] is False

    def test_send_enabled(self):
        c = WhatsAppChannel(ChannelConfig(enabled=True, base_url="https://api.whatsapp.com"))
        import asyncio
        result = asyncio.run(c.send("+551199999", "msg"))
        assert result["success"] is True

    def test_send_alert(self):
        c = WhatsAppChannel(ChannelConfig(enabled=True, base_url="https://api.whatsapp.com"))
        import asyncio
        result = asyncio.run(
            c.send_alert("+551199999", "Alert", "msg", "high", "inv1")
        )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# WebhookChannel
# ---------------------------------------------------------------------------

class TestWebhookChannel:
    def test_create_channel(self):
        c = WebhookChannel(ChannelConfig(enabled=True, webhook_url="https://hook.test"))
        assert c.config.webhook_url == "https://hook.test"

    def test_send_disabled(self):
        c = WebhookChannel(ChannelConfig(enabled=False))
        import asyncio
        result = asyncio.run(c.send({"event": "test"}))
        assert result["success"] is False

    def test_send_enabled(self):
        c = WebhookChannel(ChannelConfig(enabled=True, webhook_url="https://hook.test"))
        import asyncio
        result = asyncio.run(c.send({"event": "test"}))
        assert result["success"] is True

    def test_send_alert(self):
        c = WebhookChannel(ChannelConfig(enabled=True, webhook_url="https://hook.test"))
        import asyncio
        result = asyncio.run(
            c.send_alert("a1", "Alert", "msg", "medium", "inv1")
        )
        assert result["success"] is True
