import unittest
from notifyseat.core.models import TrackingTask, TransportType
from notifyseat.providers.registry import registry
from notifyseat.providers.simulation import SimulationProvider
from notifyseat.providers.tcdd import TCDDProvider
from notifyseat.providers.flights import FlightProvider
from notifyseat.providers.bus import BusProvider


class TestProviders(unittest.TestCase):
    def test_registry_lookup(self):
        tcdd = registry.get(TransportType.TCDD)
        self.assertIsInstance(tcdd, TCDDProvider)

        flight = registry.get(TransportType.FLIGHT)
        self.assertIsInstance(flight, FlightProvider)

        bus = registry.get(TransportType.BUS)
        self.assertIsInstance(bus, BusProvider)

        sim = registry.get(TransportType.SIMULATION)
        self.assertIsInstance(sim, SimulationProvider)

    def test_simulation_cancellation_cycle(self):
        sim = SimulationProvider()
        task = TrackingTask(
            origin="Istanbul",
            destination="Ankara",
            date="2026-09-10",
            transport_type=TransportType.SIMULATION
        )
        
        # Check 1: Sold out
        res1 = sim.check_route(task)
        self.assertFalse(res1.found)
        self.assertEqual(res1.seats_count, 0)

        # Check 2: Sold out
        res2 = sim.check_route(task)
        self.assertFalse(res2.found)

        # Check 3: Cancellation released!
        res3 = sim.check_route(task)
        self.assertTrue(res3.found)
        self.assertGreater(res3.seats_count, 0)
        self.assertEqual(len(res3.services), 1)
        self.assertIn("SIM-81001", res3.services[0].service_id)

    def test_station_search(self):
        tcdd = registry.get(TransportType.TCDD)
        results = tcdd.search_stations("Ankara")
        self.assertTrue(len(results) >= 1)
        self.assertTrue(any("Ankara Gar" in r["name"] for r in results))

        flight = registry.get(TransportType.FLIGHT)
        results_f = flight.search_stations("SAW")
        self.assertTrue(len(results_f) >= 1)
        self.assertEqual(results_f[0]["id"], "SAW")


if __name__ == "__main__":
    unittest.main()
