"""
Tests for pvSolar Reports Email Sender.
"""

from src.core.config import EmailConfig
from src.core.email_sender import EmailSender


class TestEmailSender:
    def setup_method(self):
        self.config = EmailConfig(
            enabled=True,
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_user="user@test.com",
            smtp_password="pass",
            from_address="reports@test.com",
            recipients=["admin@test.com"],
        )

    def test_create_sender(self):
        sender = EmailSender(self.config)
        assert sender.config.smtp_host == "smtp.test.com"

    def test_create_message(self):
        sender = EmailSender(self.config)
        msg = sender._create_message("Test Subject", "Test body", ["admin@test.com"])
        assert msg["Subject"] == "Test Subject"
        assert "admin@test.com" in msg["To"]

    def test_send_disabled(self):
        config = EmailConfig(enabled=False)
        sender = EmailSender(config)
        result = sender.send("Subject", "Body", ["test@test.com"])
        assert result is False

    def test_send_no_recipients(self):
        config = EmailConfig(enabled=True, recipients=[])
        sender = EmailSender(config)
        result = sender.send("Subject", "Body")
        assert result is False
