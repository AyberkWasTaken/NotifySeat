"""Notification Manager: orchestrates dispatching across all channels."""
import time
from typing import Dict, List, Optional, Any
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import AppConfig
from notifyseat.core.database import Database
from notifyseat.core.logger import logger
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.notifiers.desktop import DesktopNotifier
from notifyseat.notifiers.email import EmailNotifier
from notifyseat.notifiers.whatsapp import WhatsAppNotifier
from notifyseat.notifiers.sms import SMSNotifier
from notifyseat.notifiers.webhook import WebhookNotifier


class NotificationManager:
    """Dispatches notifications across configured channels with deduplication and throttling."""

    def __init__(self, config: AppConfig, db: Optional[Database] = None):
        self.config = config
        self.db = db
        self.notifiers: Dict[str, BaseNotifier] = {}
        self._last_notified: Dict[str, float] = {}  # task_id -> timestamp
        self._throttle_seconds = 60  # minimum seconds between alerts for the same task
        self.reload()

    def reload(self, config: Optional[AppConfig] = None):
        if config:
            self.config = config
        self.notifiers = {
            "desktop": DesktopNotifier(self.config.desktop),
            "email": EmailNotifier(self.config.email),
            "whatsapp": WhatsAppNotifier(self.config.whatsapp),
            "sms": SMSNotifier(self.config.sms),
            "webhook": WebhookNotifier(self.config.webhook)
        }

    def dispatch(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Dict[str, bool]:
        """
        Send notification to all relevant channels for the task.
        Returns dict of channel_name -> success_status.
        """
        results: Dict[str, bool] = {}
        
        # Throttling check
        if task and not force:
            last_time = self._last_notified.get(task.id, 0)
            now = time.time()
            if now - last_time < self._throttle_seconds:
                logger.info(f"Notification for task {task.id} throttled (sent {int(now - last_time)}s ago).")
                return results
            self._last_notified[task.id] = now

        # Determine which channels to send to:
        # Include task-specific channels PLUS any globally enabled channels (Email, WhatsApp, Desktop)
        target_channels = set(task.notification_channels if (task and task.notification_channels) else ["desktop"])
        if self.config.desktop.enabled:
            target_channels.add("desktop")
        if self.config.email.enabled and self.config.email.recipient_email:
            target_channels.add("email")
        if self.config.whatsapp.enabled and self.config.whatsapp.phone_number:
            target_channels.add("whatsapp")
        
        for ch_name in target_channels:
            notifier = self.notifiers.get(ch_name.lower())
            if not notifier:
                continue

            try:
                success = notifier.send(title=title, message=message, task=task, data=data)
                results[ch_name] = success
                if self.db:
                    self.db.log_notification(
                        task_id=task.id if task else "global",
                        channel=ch_name,
                        success=success,
                        title=title,
                        content=message,
                        error_message=None if success else "Failed to send or channel disabled"
                    )
            except Exception as e:
                logger.error(f"Error sending notification via {ch_name}: {e}")
                results[ch_name] = False
                if self.db:
                    self.db.log_notification(
                        task_id=task.id if task else "global",
                        channel=ch_name,
                        success=False,
                        title=title,
                        content=message,
                        error_message=str(e)
                    )

        return results

    def test_channel(self, channel_name: str) -> bool:
        """Test a specific channel."""
        notifier = self.notifiers.get(channel_name.lower())
        if not notifier:
            return False
        return notifier.test()

    def test_all(self) -> Dict[str, Dict[str, Any]]:
        """Test all channels and return structured status."""
        results = {}
        
        # Desktop
        desktop_notifier = self.notifiers.get("desktop")
        if self.config.desktop.enabled and desktop_notifier:
            ok = desktop_notifier.test()
            results["desktop"] = {"enabled": True, "success": ok, "label": "Desktop Audio & Notification"}
        else:
            results["desktop"] = {"enabled": False, "success": False, "label": "Desktop Audio & Notification"}

        # WhatsApp
        wa_notifier = self.notifiers.get("whatsapp")
        if self.config.whatsapp.enabled and self.config.whatsapp.phone_number and wa_notifier:
            ok = wa_notifier.test()
            results["whatsapp"] = {"enabled": True, "success": ok, "label": f"WhatsApp ({self.config.whatsapp.phone_number})"}
        else:
            results["whatsapp"] = {"enabled": False, "success": False, "label": "WhatsApp (Direct Mobile Alert)"}

        # Email
        email_notifier = self.notifiers.get("email")
        if self.config.email.enabled and self.config.email.recipient_email and email_notifier:
            ok = email_notifier.test()
            results["email"] = {"enabled": True, "success": ok, "label": f"Email ({self.config.email.recipient_email})"}
        else:
            results["email"] = {"enabled": False, "success": False, "label": "Email (SMTP)"}

        return results
