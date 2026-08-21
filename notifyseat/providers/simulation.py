"""Simulation / Live Demo Provider for testing seat cancellations & notifications."""
from typing import List, Dict, Any, Optional
import time
from datetime import datetime
from notifyseat.providers.base import BaseProvider
from notifyseat.core.models import TrackingTask, CheckResult, TransportType, ServiceInfo


class SimulationProvider(BaseProvider):
    """
    Simulates real-world seat cancellation dynamics.
    Ideal for demos, unit tests, and verifying notification channels.
    """

    def __init__(self):
        self._check_counts: Dict[str, int] = {}

    @property
    def transport_type(self) -> TransportType:
        return TransportType.SIMULATION

    @property
    def name(self) -> str:
        return "Live Demo / Simulation"

    def search_stations(self, query: str) -> List[Dict[str, str]]:
        return [
            {"id": "DEMO-1", "name": "Istanbul (Demo Central)", "city": "Istanbul"},
            {"id": "DEMO-2", "name": "Ankara (Demo Express)", "city": "Ankara"},
            {"id": "DEMO-3", "name": "Izmir (Demo Coast)", "city": "Izmir"}
        ]

    def get_popular_routes(self) -> List[Dict[str, str]]:
        return [
            {"origin": "Istanbul (Demo Central)", "destination": "Ankara (Demo Express)", "label": "Demo: Istanbul ➔ Ankara (Simulation)"}
        ]

    def trigger_instant_cancellation(self, task_id: str):
        """Forces the next check for this task to find available cancelled seats."""
        self._check_counts[task_id] = 2  # next check will release seats

    def check_route(self, task: TrackingTask) -> CheckResult:
        count = self._check_counts.get(task.id, 0) + 1
        self._check_counts[task.id] = count

        # Cycle: Checks 1-2 = 0 seats (Sold Out), Check 3 = 1 seat released (Cancellation!), Check 4+ = 2 seats
        if count in (1, 2):
            return CheckResult(
                task_id=task.id,
                success=True,
                found=False,
                seats_count=0,
                message="Train/Vehicle is currently fully booked (0 available seats). Watching for passenger cancellations..."
            )
        else:
            seats_released = 2
            services = [
                ServiceInfo(
                    service_id="SIM-81001",
                    service_name="Demo Express 81001 (YHT)",
                    departure_time="09:15",
                    arrival_time="13:40",
                    origin=task.origin,
                    destination=task.destination,
                    date=task.date,
                    total_available_seats=seats_released,
                    class_breakdown={"2+1 Pulman": 1, "Business": 1},
                    price=430.0,
                    currency="TRY",
                    booking_url="https://ebilet.tcddtasimacilik.gov.tr",
                    operator="NotifySeat Simulation Engine",
                    notes="🚨 PASSENGER CANCELLATION DETECTED: Seat 14A (Pulman) and Seat 04B (Business) just became available!"
                )
            ]
            return CheckResult(
                task_id=task.id,
                success=True,
                found=True,
                seats_count=seats_released,
                services=services,
                message=f"🚨 CANCELLATION DETECTED: {seats_released} seats freshly opened on {services[0].service_name}!"
            )
