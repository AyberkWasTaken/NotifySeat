"""WhatsApp (CallMeBot) notification provider."""
import re
import html
import requests
from typing import Optional, Dict, Any
from notifyseat.notifiers.base import BaseNotifier
from notifyseat.core.models import TrackingTask
from notifyseat.core.config import WhatsAppConfig
from notifyseat.core.logger import logger


def normalize_phone_number(phone: str) -> str:
    """Normalizes Turkish and international phone numbers to E.164 (+905xxxxxxxxx)."""
    if not phone:
        return ""
    raw = phone.strip()
    digits = "".join(c for c in raw if c.isdigit())
    if raw.startswith("+"):
        return "+" + digits
    if len(digits) == 10 and digits.startswith("5"):
        return "+90" + digits
    if len(digits) == 11 and digits.startswith("05"):
        return "+90" + digits[1:]
    if len(digits) == 12 and digits.startswith("90"):
        return "+" + digits
    return "+" + digits


def extract_clean_error(raw_text: str) -> str:
    """Extracts a clean, human-readable error string from raw HTML gateway responses."""
    if not raw_text:
        return "Empty response from server"
    
    # Strip HTML and decode entities
    unescaped = html.unescape(raw_text)
    clean = re.sub(r"<[^>]+>", " ", unescaped)
    clean = re.sub(r"\s+", " ", clean).strip()

    # Look for specific error or service notices
    for marker in [
        "Service is down",
        "API key is invalid",
        "API key not found",
        "Phone number not registered",
        "Daily limit reached",
        "Error",
        "error",
        "Invalid",
        "Sorry for the inconvenience"
    ]:
        if marker in clean:
            idx = clean.find(marker)
            return clean[idx:].strip()

    return clean if len(clean) <= 150 else clean[:150] + "..."


class WhatsAppNotifier(BaseNotifier):
    """Sends notifications directly to user's WhatsApp via CallMeBot gateway."""

    def __init__(self, config: WhatsAppConfig):
        self.config = config

    @property
    def channel_name(self) -> str:
        return "whatsapp"

    def send(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.config.enabled or not self.config.phone_number or not self.config.apikey:
            return False

        phone = normalize_phone_number(self.config.phone_number)
        text = message.strip()

        params = {
            "phone": phone,
            "text": text,
            "apikey": self.config.apikey
        }

        try:
            r = requests.get("https://api.callmebot.com/whatsapp.php", params=params, timeout=12)
            if r.status_code == 200 and "error" not in r.text.lower() and "service is down" not in r.text.lower():
                return True
            else:
                clean_err = extract_clean_error(r.text)
                logger.error(f"WhatsApp notification failed: [{r.status_code}] {clean_err}")
                return False
        except Exception as e:
            logger.error(f"WhatsApp notification network error: {e}")
            return False

    def test(self) -> bool:
        return self.send(
            title="NotifySeat Test Alert",
            message="🎉 WhatsApp notification is connected and working! Ready to catch seat cancellations."
        )

