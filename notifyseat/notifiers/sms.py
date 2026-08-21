"""SMS notification provider (Netgsm, Twilio, Webhook)."""
import urllib.request
import urllib.parse
import json
import base64
from typing import Optional, Dict, Any
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import SMSConfig
from notifyseat.core.logger import logger


class SMSNotifier(BaseNotifier):
    """Sends SMS notifications using Netgsm or Twilio."""

    def __init__(self, config: SMSConfig):
        self.config = config

    @property
    def channel_name(self) -> str:
        return "sms"

    def send(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.config.enabled or not self.config.phone_number:
            return False

        full_message = f"[NotifySeat] {title}: {message}"
        if task:
            full_message += f" ({task.origin}->{task.destination}, {task.date})"
        if data and data.get("booking_url"):
            full_message += f" Link: {data['booking_url']}"

        if self.config.provider == "netgsm":
            return self._send_netgsm(full_message)
        elif self.config.provider == "twilio":
            return self._send_twilio(full_message)
        return False

    def test(self) -> bool:
        return self.send(
            title="Test Alert",
            message="NotifySeat SMS test message!"
        )

    def _send_netgsm(self, text: str) -> bool:
        """Send SMS via Netgsm REST API (Turkey)."""
        url = "https://api.netgsm.com.tr/sms/send/get"
        params = {
            "usercode": self.config.api_key,
            "password": self.config.api_secret,
            "gsmno": self.config.phone_number.replace("+", "").replace(" ", ""),
            "message": text,
            "msgheader": self.config.sender_header or self.config.api_key
        }
        encoded_url = f"{url}?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(encoded_url, headers={"User-Agent": "NotifySeat"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = resp.read().decode("utf-8")
                # Netgsm returns "00 12345678" on success
                return result.startswith("00") or "00" in result
        except Exception as e:
            logger.error(f"Netgsm SMS error: {e}")
            return False

    def _send_twilio(self, text: str) -> bool:
        """Send SMS via Twilio API."""
        account_sid = self.config.api_key
        auth_token = self.config.api_secret
        from_number = self.config.sender_header
        to_number = self.config.phone_number

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        data = urllib.parse.urlencode({
            "From": from_number,
            "To": to_number,
            "Body": text
        }).encode("utf-8")

        auth_str = f"{account_sid}:{auth_token}"
        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

        try:
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Basic {b64_auth}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 201)
        except Exception as e:
            logger.error(f"Twilio SMS error: {e}")
            return False
