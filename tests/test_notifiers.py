import unittest
import tempfile
from pathlib import Path
from notifyseat.core.models import TrackingTask, TransportType
from notifyseat.core.config import AppConfig
from notifyseat.core.database import Database
from notifyseat.notifiers.manager import NotificationManager
from notifyseat.notifiers.desktop import DesktopNotifier


class TestNotifiers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)
        self.config = AppConfig()
        self.config.desktop.enabled = True
        self.config.desktop.sound_enabled = False  # disable sound in unit test
        self.manager = NotificationManager(self.config, self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_desktop_send(self):
        desktop = DesktopNotifier(self.config.desktop)
        res = desktop.send("Test Title", "Test Message")
        self.assertTrue(res)

    def test_manager_dispatch(self):
        task = TrackingTask(
            name="Ankara Test",
            origin="Istanbul",
            destination="Ankara",
            date="2026-09-01",
            notification_channels=["desktop"]
        )
        results = self.manager.dispatch(
            title="Seat Found!",
            message="1 seat available on YHT 81001",
            task=task,
            data={"seats_count": 1, "booking_url": "https://ebilet.tcddtasimacilik.gov.tr"}
        )
        self.assertIn("desktop", results)
        self.assertTrue(results["desktop"])

        # Check DB log
        history = self.db.list_notification_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["task_id"], task.id)
        self.assertEqual(history[0]["channel"], "desktop")


if __name__ == "__main__":
    unittest.main()
