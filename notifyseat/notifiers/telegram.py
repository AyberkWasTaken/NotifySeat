"""Telegram Bot notification provider."""
import urllib.request
import urllib.parse
import json
from typing import Optional, Dict, Any
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import TelegramConfig
from notifyseat.core.logger import logger


class TelegramNotifier(BaseNotifier):
    """Sends notifications via Telegram Bot API."""

    def __init__(self, config: TelegramConfig):
        self.config = config

    @property
    def channel_name(self) -> str:
        return "telegram"

    def send(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.config.enabled or not self.config.bot_token or not self.config.chat_id:
            return False

        formatted_text = f"🚨 <b>{title}</b>\n\n{message}"
        if task:
            formatted_text += f"\n\n📍 <i>Route:</i> <code>{task.origin} ➔ {task.destination}</code>"
            formatted_text += f"\n📅 <i>Date:</i> <code>{task.date}</code>"

        if data and data.get("booking_url"):
            formatted_text += f"\n\n🔗 <a href='{data['booking_url']}'>Click here to book immediately</a>"

        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        payload = {
            "chat_id": self.config.chat_id,
            "text": formatted_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("ok", False)
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
            return False

    def test(self) -> bool:
        return self.send(
            title="NotifySeat - Test Alert",
            message="Telegram bot integration is working properly! 🎉"
        )
