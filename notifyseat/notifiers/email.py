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

        # Plain text version
        text_content = f"{title}\n\n{message}\n"
        if task:
            text_content += f"\nRoute: {task.origin} -> {task.destination}\nDate: {task.date}\nTransport: {task.transport_type.upper()}\n"
        if data and data.get("booking_url"):
            text_content += f"\nBooking Link: {data['booking_url']}\n"

        # HTML version
        booking_btn = ""
        if data and data.get("booking_url"):
            booking_btn = f"""
            <div style="margin-top: 20px;">
                <a href="{data['booking_url']}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">
                    Book Seats Now ➔
                </a>
            </div>
            """

        task_info = ""
        if task:
            task_info = f"""
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr><td style="padding: 6px; color: #6b7280;">Route:</td><td style="padding: 6px; font-weight: bold;">{task.origin} ➔ {task.destination}</td></tr>
                <tr><td style="padding: 6px; color: #6b7280;">Date:</td><td style="padding: 6px; font-weight: bold;">{task.date}</td></tr>
                <tr><td style="padding: 6px; color: #6b7280;">Transport:</td><td style="padding: 6px; font-weight: bold;">{task.transport_type.upper()}</td></tr>
            </table>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
                <div style="background: #1e293b; color: white; padding: 20px; text-align: center;">
                    <h1 style="margin: 0; font-size: 20px;">🚨 NotifySeat Alert</h1>
                </div>
                <div style="padding: 24px;">
                    <h2 style="color: #111827; margin-top: 0;">{title}</h2>
                    <p style="color: #374151; font-size: 16px; line-height: 1.5;">{message}</p>
                    {task_info}
                    {booking_btn}
                </div>
                <div style="background: #f8fafc; padding: 12px; text-align: center; color: #94a3b8; font-size: 12px;">
                    Sent locally by NotifySeat for Ayberk
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
