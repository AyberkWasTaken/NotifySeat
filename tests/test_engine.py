import unittest
import tempfile
import time
from pathlib import Path
from notifyseat.core.models import TrackingTask, TransportType, TaskStatus
from notifyseat.core.config import AppConfig
from notifyseat.core.database import Database
from notifyseat.notifiers.manager import NotificationManager
from notifyseat.engine.scheduler import EngineScheduler
from notifyseat.providers.registry import registry
from notifyseat.providers.simulation import SimulationProvider


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test.db")
        self.config = AppConfig()
        self.config.desktop.enabled = False
        self.notifier_mgr = NotificationManager(self.config, self.db)
        self.scheduler = EngineScheduler(self.db, self.config, self.notifier_mgr)

    def tearDown(self):
        self.scheduler.stop()
        self.temp_dir.cleanup()

    def test_worker_and_simulation_execution(self):
        task = TrackingTask(
            name="Demo Tracker",
            origin="Istanbul",
            destination="Ankara",
            date="2026-09-01",
            transport_type=TransportType.SIMULATION,
            check_interval_seconds=5
        )
        self.db.create_task(task)

        events = []
        self.scheduler.subscribe_events(lambda evt, data: events.append((evt, data)))

        # Run check 1
        res1 = self.scheduler.worker.execute_task(task)
        self.assertFalse(res1.found)
        self.assertEqual(res1.seats_count, 0)

        # Run check 2
        res2 = self.scheduler.worker.execute_task(task)
        self.assertFalse(res2.found)

        # Run check 3 -> seats open
        res3 = self.scheduler.worker.execute_task(task)
        self.assertTrue(res3.found)
        self.assertGreater(res3.seats_count, 0)

        # Verify DB updated
        updated = self.db.get_task(task.id)
        self.assertEqual(updated.last_found_seats, res3.seats_count)
        self.assertIsNotNone(updated.last_checked_at)

        # Verify event fired
        seat_found_events = [e for e in events if e[0] == "seats_found"]
        self.assertTrue(len(seat_found_events) >= 1)

    def test_rate_limiting_and_backoff(self):
        task = TrackingTask(
            name="Rate Limit Test",
            origin="Istanbul",
            destination="Eskisehir",
            date="2026-09-01",
            transport_type=TransportType.SIMULATION,
            check_interval_seconds=1
        )
        self.db.create_task(task)

        # Mock rate limited result
        from unittest.mock import patch, MagicMock
        from notifyseat.core.models import CheckResult

        mock_rate_limited = CheckResult(
            task_id=task.id,
            success=False,
            found=False,
            seats_count=0,
            rate_limited=True,
            backoff_seconds=10,
            message="TCDD sunucusu yoğunluk bildirdi."
        )

        events = []
        self.scheduler.subscribe_events(lambda evt, data: events.append((evt, data)))

        with patch.object(self.scheduler.worker, 'execute_task', return_value=mock_rate_limited):
            self.scheduler.start()
            time.sleep(1.2)
            self.assertTrue(self.scheduler.is_in_backoff())
            self.assertGreater(self.scheduler.backoff_remaining_seconds(), 0)

            # Check humanized event was fired
            backoff_events = [e for e in events if e[0] == "rate_limit_backoff"]
            self.assertTrue(len(backoff_events) >= 1)
            backoff_msg = backoff_events[0][1]["message"]
            self.assertIn("TCDD sunucuları", backoff_msg)
            self.assertNotIn("[ERROR]", backoff_msg)
            self.assertNotIn("RATE_LIMIT_EXCEEDED", backoff_msg)


if __name__ == "__main__":
    unittest.main()
