"""Discord Webhook notification provider."""
import urllib.request
import json
from typing import Optional, Dict, Any
from datetime import datetime
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import DiscordConfig
from notifyseat.core.logger import logger


class DiscordNotifier(BaseNotifier):
    """Sends notifications via Discord Webhook."""

    def __init__(self, config: DiscordConfig):
        self.config = config

    @property
    def channel_name(self) -> str:
        return "discord"

    def send(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.config.enabled or not self.config.webhook_url:
            return False

        fields = []
        if task:
            fields.append({"name": "Route", "value": f"{task.origin} ➔ {task.destination}", "inline": True})
            fields.append({"name": "Date", "value": task.date, "inline": True})
            fields.append({"name": "Transport", "value": task.transport_type.upper(), "inline": True})

        if data:
            if "seats_count" in data:
                fields.append({"name": "Seats Available", "value": str(data["seats_count"]), "inline": True})
            if "service_name" in data:
                fields.append({"name": "Service / Train / Flight", "value": str(data["service_name"]), "inline": True})
            if "departure_time" in data:
                fields.append({"name": "Time", "value": str(data["departure_time"]), "inline": True})

        embed = {
            "title": f"🚨 {title}",
            "description": message,
            "color": 3447003,  # Blue / Alert
            "fields": fields,
            "footer": {"text": "NotifySeat - Local Seat Availability Notifier"},
            "timestamp": datetime.now().isoformat()
        }

        if data and data.get("booking_url"):
            embed["url"] = data["booking_url"]

        payload = {
            "username": "NotifySeat",
            "avatar_url": "https://img.icons8.com/color/96/train.png",
            "embeds": [embed]
        }

        try:
            req = urllib.request.Request(
                self.config.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "NotifySeat-Bot/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status in (200, 204)
        except Exception as e:
            logger.error(f"Discord notification error: {e}")
            return False

    def test(self) -> bool:
        return self.send(
            title="NotifySeat - Test Alert",
            message="Discord webhook notification integration is working properly! 🎉"
        )
