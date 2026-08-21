"""Scheduler and Background Daemon Engine for NotifySeat."""
import threading
import time
import random
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from notifyseat.core.models import TrackingTask, TaskStatus
from notifyseat.core.database import Database
from notifyseat.core.config import AppConfig
from notifyseat.core.logger import logger
from notifyseat.notifiers.manager import NotificationManager
from notifyseat.engine.worker import TaskWorker


class EngineScheduler:
    """Manages background threads and polling schedules for active tracking tasks."""

    def __init__(self, db: Database, config: AppConfig, notifier_mgr: Optional[NotificationManager] = None):
        self.db = db
        self.config = config
        self.notifier_mgr = notifier_mgr or NotificationManager(config, db)
        self.worker = TaskWorker(db, self.notifier_mgr, self._handle_worker_event)
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._event_subscribers: List[Callable[[str, Dict[str, Any]], None]] = []
        self._last_run_times: Dict[str, float] = {}

    def subscribe_events(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Subscribe to real-time engine events (for CLI monitor and Web GUI live stream)."""
        self._event_subscribers.append(callback)

    def _handle_worker_event(self, event_type: str, data: Dict[str, Any]):
        for sub in self._event_subscribers:
            try:
                sub(event_type, data)
            except Exception:
                pass

    def start(self):
        """Starts the background scheduler thread."""
        with self._lock:
            if self._running:
                logger.info("Scheduler is already running.")
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True, name="NotifySeatScheduler")
            self._thread.start()
            logger.info("🚀 NotifySeat Background Engine started.")
            self._handle_worker_event("engine_started", {"timestamp": datetime.now().isoformat()})

    def stop(self):
        """Stops the background scheduler thread."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            logger.info("🛑 Stopping NotifySeat Background Engine...")
            self._handle_worker_event("engine_stopped", {"timestamp": datetime.now().isoformat()})

    def is_running(self) -> bool:
        return self._running

    def trigger_task_now(self, task_id: str) -> bool:
        """Executes an immediate manual check for a specific task."""
        task = self.db.get_task(task_id)
        if not task:
            return False
        self.worker.execute_task(task)
        return True

    def _loop(self):
        """Main daemon loop."""
        while self._running:
            try:
                active_tasks = self.db.list_tasks(status=TaskStatus.ACTIVE)
                now = time.time()

                for task in active_tasks:
                    if not self._running:
                        break

                    interval = max(5, task.check_interval_seconds or self.config.default_check_interval)
                    last_time = self._last_run_times.get(task.id, 0)

                    # Check if interval elapsed
                    if now - last_time >= interval:
                        try:
                            # Apply slight jitter to prevent pattern recognition
                            jitter = random.uniform(-1.0, 1.0)
                            time.sleep(max(0.1, jitter + 0.2))
                            
                            self.worker.execute_task(task)
                            self._last_run_times[task.id] = time.time()
                        except Exception as e:
                            logger.error(f"Error checking task {task.name} ({task.id}): {e}")

                # Sleep brief interval between task sweeps
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error in scheduler main loop: {e}")
                time.sleep(3)
