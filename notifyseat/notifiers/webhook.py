"""Custom HTTP Webhook notification provider."""
import urllib.request
import json
from typing import Optional, Dict, Any
from datetime import datetime
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import WebhookConfig
from notifyseat.core.logger import logger


class WebhookNotifier(BaseNotifier):
    """Sends notifications to custom Webhooks (Home Assistant, Zapier, IFTTT, n8n)."""

    def __init__(self, config: WebhookConfig):
        self.config = config

    @property
    def channel_name(self) -> str:
        return "webhook"

    def send(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.config.enabled or not self.config.url:
            return False

        payload = {
            "event": "seat_available",
            "title": title,
            "message": message,
            "task": task.to_dict() if task else None,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NotifySeat-Webhook/1.0"
        }
        if self.config.custom_headers:
            headers.update(self.config.custom_headers)

        try:
            req = urllib.request.Request(
                self.config.url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method=self.config.method or "POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except Exception as e:
            logger.error(f"Webhook notification error: {e}")
            return False

    def test(self) -> bool:
        return self.send(
            title="NotifySeat - Test Webhook",
            message="Webhook test event successfully triggered!"
        )
