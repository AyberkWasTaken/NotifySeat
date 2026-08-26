import unittest
import tempfile
import os
from pathlib import Path
from notifyseat.core.models import TrackingTask, TransportType, TaskStatus, ServiceInfo
from notifyseat.core.config import ConfigManager, AppConfig
from notifyseat.core.database import Database


class TestCore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.db = Database(self.db_path)
        self.cfg_mgr = ConfigManager(self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_creation_and_db(self):
        task = TrackingTask(
            name="Ankara Test",
            transport_type=TransportType.TCDD,
            origin="İstanbul(Söğütlüçeşme)",
            destination="Ankara Gar",
            date="2026-09-10",
            notification_channels=["desktop", "whatsapp"]
        )
        saved = self.db.create_task(task)
        self.assertEqual(saved.id, task.id)

        loaded = self.db.get_task(task.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.origin, "İstanbul(Söğütlüçeşme)")
        self.assertEqual(loaded.destination, "Ankara Gar")
        self.assertEqual(loaded.transport_type, TransportType.TCDD)
        self.assertEqual(loaded.notification_channels, ["desktop", "whatsapp"])

    def test_config_save_load(self):
        cfg = self.cfg_mgr.get()
        cfg.whatsapp.enabled = True
        cfg.whatsapp.phone_number = "+905551112233"
        cfg.user_name = "Ayberk"
        self.cfg_mgr.save(cfg)

        new_mgr = ConfigManager(self.config_path)
        loaded = new_mgr.get()
        self.assertTrue(loaded.whatsapp.enabled)
        self.assertEqual(loaded.whatsapp.phone_number, "+905551112233")
        self.assertEqual(loaded.user_name, "Ayberk")

    def test_stats_and_logs(self):
        task = TrackingTask(
            origin="Izmir",
            destination="Istanbul",
            date="2026-09-01"
        )
        self.db.create_task(task)
        self.db.log_check(task.id, success=True, seats_found=2, status="FOUND", message="2 seats found!")
        stats = self.db.get_stats()
        self.assertEqual(stats["total_tasks"], 1)
        self.assertEqual(stats["total_checks"], 1)
        self.assertEqual(stats["seats_found_count"], 1)


if __name__ == "__main__":
    unittest.main()
