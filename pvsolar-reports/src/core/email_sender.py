"""
Email Sender Module.

Sends report notifications via email.
"""

import asyncio
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog
from src.core.config import EmailConfig

logger = structlog.get_logger(__name__)


class EmailSender:
    """
    Sends emails with report attachments.

    Features:
    - Async email sending
    - Multiple attachments
    - HTML email body
    - Error handling
    """

    def __init__(self, config: EmailConfig):
        self.config = config

    def _create_message(
        self,
        subject: str,
        body: str,
        recipients: list[str],
        attachments: list[str] | None = None,
    ) -> MIMEMultipart:
        msg = MIMEMultipart()
        msg["From"] = self.config.from_address
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #10B981;">pvSolar Reports</h2>
            <p>{body}</p>
            <hr style="border: 1px solid #E5E7EB;">
            <p style="color: #6B7280; font-size: 12px;">
                This is an automated report from pvSolar Reports v1.0.0
            </p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        if attachments:
            for filepath in attachments:
                try:
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    filename = filepath.split("/")[-1].split("\\")[-1]
                    part.add_header("Content-Disposition", f"attachment; filename={filename}")
                    msg.attach(part)
                except Exception as e:
                    logger.error("email.attachment_error", filepath=filepath, error=str(e))

        return msg

    def send(
        self,
        subject: str,
        body: str,
        recipients: list[str] | None = None,
        attachments: list[str] | None = None,
    ) -> bool:
        if not self.config.enabled:
            logger.info("email.disabled")
            return False

        recipients = recipients or self.config.recipients
        if not recipients:
            logger.warning("email.no_recipients")
            return False

        msg = self._create_message(subject, body, recipients, attachments)

        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls()
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_address, recipients, msg.as_string())

            logger.info("email.sent", subject=subject, recipients=recipients)
            return True

        except Exception as e:
            logger.error("email.send_error", error=str(e))
            return False

    async def send_async(
        self,
        subject: str,
        body: str,
        recipients: list[str] | None = None,
        attachments: list[str] | None = None,
    ) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.send(subject, body, recipients, attachments))
