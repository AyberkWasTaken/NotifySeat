"""Base class for all notification providers."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from notifyseat.core.models import TrackingTask


class BaseNotifier(ABC):
    """Abstract base class for notification channels."""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Name of the channel (e.g. desktop, telegram, discord, email, sms, webhook)."""
        pass

    @abstractmethod
    def send(
        self,
        title: str,
        message: str,
        task: Optional[TrackingTask] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a notification. Returns True if successfully sent."""
        pass

    @abstractmethod
    def test(self) -> bool:
        """Send a test message to verify the configuration."""
        pass
