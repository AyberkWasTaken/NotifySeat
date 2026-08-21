"""Provider Registry and Factory."""
from typing import Dict, List, Optional
from notifyseat.core.models import TransportType
from notifyseat.providers.base import BaseProvider
from notifyseat.providers.tcdd import TCDDProvider
from notifyseat.providers.flights import FlightProvider
from notifyseat.providers.bus import BusProvider
from notifyseat.providers.simulation import SimulationProvider


class ProviderRegistry:
    """Registry managing available transport providers."""

    def __init__(self):
        self._providers: Dict[TransportType, BaseProvider] = {
            TransportType.TCDD: TCDDProvider(),
            TransportType.FLIGHT: FlightProvider(),
            TransportType.BUS: BusProvider(),
            TransportType.SIMULATION: SimulationProvider(),
        }

    def get(self, transport_type: TransportType) -> BaseProvider:
        return self._providers.get(transport_type, self._providers[TransportType.SIMULATION])

    def list_providers(self) -> List[Dict[str, str]]:
        return [
            {"type": p.transport_type.value, "name": p.name}
            for p in self._providers.values()
        ]


# Singleton instance
registry = ProviderRegistry()
