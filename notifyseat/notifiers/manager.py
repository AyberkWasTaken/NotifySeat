"""Notification Manager: orchestrates dispatching across all channels."""
import time
from typing import Dict, List, Optional, Any
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import AppConfig
from notifyseat.core.database import Database
from notifyseat.core.logger import logger
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.notifiers.desktop import DesktopNotifier
from notifyseat.notifiers.telegram import TelegramNotifier
from notifyseat.notifiers.discord import DiscordNotifier
from notifyseat.notifiers.email import EmailNotifier
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
            "telegram": TelegramNotifier(self.config.telegram),
            "discord": DiscordNotifier(self.config.discord),
            "email": EmailNotifier(self.config.email),
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

        # Determine which channels to send to
        target_channels = task.notification_channels if (task and task.notification_channels) else ["desktop"]
        
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
