"""Base Transport Provider interface."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from notifyseat.core.models import TrackingTask, CheckResult, TransportType, ServiceInfo


class BaseProvider(ABC):
    """Abstract base class for all transport providers (Train, Flight, Bus, etc.)."""

    @property
    @abstractmethod
    def transport_type(self) -> TransportType:
        """Type of transport."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the transport provider."""
        pass

    @abstractmethod
    def search_stations(self, query: str) -> List[Dict[str, str]]:
        """Search for matching stations, airports, or terminals."""
        pass

    @abstractmethod
    def check_route(self, task: TrackingTask) -> CheckResult:
        """Check availability for a given tracking task."""
        pass

    @abstractmethod
    def get_popular_routes(self) -> List[Dict[str, str]]:
        """Return a list of common/popular routes for quick selection."""
        pass
