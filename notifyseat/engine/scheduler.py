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
        self._task_next_delays: Dict[str, float] = {}
        
        # Anti-ban & rate-limit backoff management
        self._backoff_until: float = 0.0
        self._consecutive_rate_limits: int = 0
        self._was_in_backoff: bool = False

    def subscribe_events(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Subscribe to real-time engine events (for CLI monitor and Web GUI live stream)."""
        self._event_subscribers.append(callback)

    def _handle_worker_event(self, event_type: str, data: Dict[str, Any]):
        for sub in self._event_subscribers:
            try:
                sub(event_type, data)
            except Exception:
                pass

    def is_in_backoff(self) -> bool:
        return time.time() < self._backoff_until

    def backoff_remaining_seconds(self) -> int:
        return max(0, int(self._backoff_until - time.time()))

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
        """Main daemon loop with humanized jitter, multi-task staggering, and anti-ban backoff."""
        while self._running:
            try:
                now = time.time()

                # Handle active rate-limit backoff
                if now < self._backoff_until:
                    self._was_in_backoff = True
                    time.sleep(1)
                    continue
                elif self._was_in_backoff:
                    self._was_in_backoff = False
                    recovery_msg = "TCDD güvenlik dinlenmesi tamamlandı. Bilet kontrolleri normal hızında yeniden başladı."
                    logger.info(recovery_msg)
                    self._handle_worker_event("rate_limit_recovered", {
                        "message": recovery_msg,
                        "timestamp": datetime.now().isoformat()
                    })

                active_tasks = self.db.list_tasks(status=TaskStatus.ACTIVE)

                for i, task in enumerate(active_tasks):
                    if not self._running or time.time() < self._backoff_until:
                        break

                    base_interval = max(30, task.check_interval_seconds or self.config.default_check_interval)
                    last_time = self._last_run_times.get(task.id, 0)
                    planned_delay = self._task_next_delays.get(task.id, base_interval)

                    # Check if target interval elapsed
                    if now - last_time >= planned_delay:
                        try:
                            result = self.worker.execute_task(task)
                            self._last_run_times[task.id] = time.time()

                            # Compute next randomized interval with humanized jitter (+- 10-15s)
                            jitter = random.uniform(-10.0, 15.0)
                            self._task_next_delays[task.id] = max(30.0, base_interval + jitter)

                            # Handle rate limit triggered by provider
                            if result and getattr(result, "rate_limited", False):
                                base_backoff = result.backoff_seconds or 180
                                backoff_duration = min(600, int(base_backoff * (1.5 ** self._consecutive_rate_limits)))
                                self._backoff_until = time.time() + backoff_duration
                                self._consecutive_rate_limits += 1

                                minutes = max(1, round(backoff_duration / 60))
                                backoff_msg = (
                                    f"TCDD sunucuları kısa süreli yoğunluk bildirdi. "
                                    f"IP adresinizi korumak ve güvenli kalmak için {minutes} dakika mola veriyoruz. "
                                    f"Süre bitince kontroller otomatik olarak kaldığı yerden devam edecek."
                                )
                                logger.warning(backoff_msg)
                                self._handle_worker_event("rate_limit_backoff", {
                                    "task_id": task.id,
                                    "task_name": task.name,
                                    "backoff_seconds": backoff_duration,
                                    "minutes": minutes,
                                    "message": backoff_msg,
                                    "timestamp": datetime.now().isoformat()
                                })
                                break
                            elif result and result.success:
                                self._consecutive_rate_limits = 0

                            # Stagger between multiple tasks (3-5s space) to avoid concurrent bursts
                            if len(active_tasks) > 1 and i < len(active_tasks) - 1:
                                time.sleep(random.uniform(2.5, 5.0))

                        except Exception as e:
                            logger.error(f"Error checking task {task.name} ({task.id}): {e}")

                # Brief idle sleep between sweep evaluations
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error in scheduler main loop: {e}")
                time.sleep(3)
