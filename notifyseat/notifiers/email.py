"""Email (SMTP) notification provider."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import EmailConfig
from notifyseat.core.logger import logger


class EmailNotifier(BaseNotifier):
    """Sends notifications via SMTP (Gmail, Outlook, custom SMTP server)."""

    def __init__(self, config: EmailConfig):
        self.config = config

    @property
    def channel_name(self) -> str:
        return "email"

    def send(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.config.enabled or not self.config.recipient_email:
            return False

        sender = self.config.sender_email or self.config.username
        recipient = self.config.recipient_email

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[NotifySeat] {title}"
        msg["From"] = f"NotifySeat <{sender}>"
        msg["To"] = recipient

        # Plain text version (clean format)
        text_content = message.strip()

        # HTML version
        booking_url = (data and data.get("booking_url")) or "https://ebilet.tcddtasimacilik.gov.tr"
        booking_btn = f"""
        <div style="margin-top: 25px; text-align: center;">
            <a href="{booking_url}" style="background-color: #2563eb; color: white; padding: 12px 28px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 15px; display: inline-block;">
                TCDD'den Bilet Al ➔
            </a>
        </div>
        """

        formatted_msg_html = message.strip().replace("\n", "<br>")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px;">
            <div style="max-width: 520px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                <div style="background: #1e293b; color: white; padding: 18px 24px; text-align: center;">
                    <h2 style="margin: 0; font-size: 18px;">🚨 NotifySeat İptal Bilet Bildirimi</h2>
                </div>
                <div style="padding: 24px; color: #1f2937; font-size: 15px; line-height: 1.6;">
                    {formatted_msg_html}
                    {booking_btn}
                </div>
                <div style="background: #f8fafc; padding: 12px; text-align: center; color: #94a3b8; font-size: 12px;">
                    NotifySeat Otomatik Koltuk Takip Sistemi
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        try:
            if self.config.smtp_port == 465:
                server = smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=15)
                if self.config.use_tls:
                    server.starttls()

            if self.config.username and self.config.password:
                server.login(self.config.username, self.config.password)

            server.sendmail(sender, [recipient], msg.as_string())
            server.quit()
            return True
        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False

    def test(self) -> bool:
        return self.send(
            title="NotifySeat - Test Email",
            message="SMTP Email integration is working properly! 🎉"
        )
