import unittest
import threading
import time
import urllib.request
import json
import tempfile
from pathlib import Path
from notifyseat.core.database import Database
from notifyseat.core.config import ConfigManager
from notifyseat.notifiers.manager import NotificationManager
from notifyseat.engine.scheduler import EngineScheduler
from notifyseat.web.server import NotifySeatHTTPHandler, ThreadedHTTPServer, SSEManager


class TestWebServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db = Database(Path(cls.temp_dir.name) / "test.db")
        cls.config_mgr = ConfigManager(Path(cls.temp_dir.name) / "config.json")
        cls.cfg = cls.config_mgr.get()
        cls.cfg.desktop.enabled = False
        cls.notifier_mgr = NotificationManager(cls.cfg, cls.db)
        cls.scheduler = EngineScheduler(cls.db, cls.cfg, cls.notifier_mgr)
        cls.sse_mgr = SSEManager()

        NotifySeatHTTPHandler.db = cls.db
        NotifySeatHTTPHandler.config_mgr = cls.config_mgr
        NotifySeatHTTPHandler.scheduler = cls.scheduler
        NotifySeatHTTPHandler.notifier_mgr = cls.notifier_mgr
        NotifySeatHTTPHandler.sse_mgr = cls.sse_mgr

        cls.port = 18090
        cls.httpd = ThreadedHTTPServer(("127.0.0.1", cls.port), NotifySeatHTTPHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.scheduler.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.temp_dir.cleanup()

    def test_get_index_and_stats(self):
        # Index HTML
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("NotifySeat", content)

        # Stats API
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/stats") as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("total_tasks", data)

    def test_tasks_crud_api(self):
        # Create task via POST
        payload = json.dumps({
            "transport_type": "tcdd",
            "origin": "İstanbul(Söğütlüçeşme)",
            "destination": "Ankara Gar",
            "date": "2026-09-15",
            "check_interval_seconds": 25,
            "notification_channels": ["desktop"]
        }).encode("utf-8")

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/tasks",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 201)
            task_data = json.loads(resp.read().decode("utf-8"))
            task_id = task_data["id"]
            self.assertEqual(task_data["origin"], "İstanbul(Söğütlüçeşme)")

        # List tasks
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/tasks") as resp:
            tasks = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(len(tasks) >= 1)

        # Delete task
        req_del = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/tasks/{task_id}",
            method="DELETE"
        )
        with urllib.request.urlopen(req_del) as resp:
            self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main()
