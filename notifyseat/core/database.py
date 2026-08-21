"""SQLite Database Layer for NotifySeat."""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from notifyseat.core.models import TrackingTask, TaskStatus, TransportType


DEFAULT_DB_PATH = Path.home() / ".notifyseat" / "notifyseat.db"


class Database:
    """Manages local SQLite database operations."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    transport_type TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    origin_id TEXT,
                    destination TEXT NOT NULL,
                    destination_id TEXT,
                    date TEXT NOT NULL,
                    time_filter TEXT,
                    min_seats INTEGER DEFAULT 1,
                    seat_class TEXT DEFAULT 'ANY',
                    check_interval_seconds INTEGER DEFAULT 30,
                    notification_channels TEXT DEFAULT '["desktop"]',
                    status TEXT DEFAULT 'active',
                    last_checked_at TEXT,
                    last_found_seats INTEGER DEFAULT 0,
                    last_service_info TEXT,
                    created_at TEXT NOT NULL,
                    auto_stop_on_found INTEGER DEFAULT 0
                )
            """)

            # Check logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS check_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    seats_found INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    details_json TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
            """)

            # Notification history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    error_message TEXT
                )
            """)

            conn.commit()

    # --- Task Operations ---

    def create_task(self, task: TrackingTask) -> TrackingTask:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (
                    id, name, transport_type, origin, origin_id,
                    destination, destination_id, date, time_filter,
                    min_seats, seat_class, check_interval_seconds,
                    notification_channels, status, last_checked_at,
                    last_found_seats, last_service_info, created_at,
                    auto_stop_on_found
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.name,
                task.transport_type.value,
                task.origin,
                task.origin_id,
                task.destination,
                task.destination_id,
                task.date,
                task.time_filter,
                task.min_seats,
                task.seat_class,
                task.check_interval_seconds,
                json.dumps(task.notification_channels),
                task.status.value,
                task.last_checked_at,
                task.last_found_seats,
                json.dumps(task.last_service_info) if task.last_service_info else None,
                task.created_at,
                1 if task.auto_stop_on_found else 0
            ))
            conn.commit()
        return task

    def get_task(self, task_id: str) -> Optional[TrackingTask]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[TrackingTask]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status.value,))
            else:
                cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [self._row_to_task(r) for r in rows]

    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status.value, task_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_task_check_state(self, task_id: str, last_checked: str, found_seats: int, service_info: Optional[Dict[str, Any]], status: Optional[TaskStatus] = None) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    UPDATE tasks 
                    SET last_checked_at = ?, last_found_seats = ?, last_service_info = ?, status = ?
                    WHERE id = ?
                """, (last_checked, found_seats, json.dumps(service_info) if service_info else None, status.value, task_id))
            else:
                cursor.execute("""
                    UPDATE tasks 
                    SET last_checked_at = ?, last_found_seats = ?, last_service_info = ?
                    WHERE id = ?
                """, (last_checked, found_seats, json.dumps(service_info) if service_info else None, task_id))
            conn.commit()
            return cursor.rowcount > 0

    def delete_task(self, task_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            cursor.execute("DELETE FROM check_logs WHERE task_id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --- Logs & Notifications ---

    def log_check(self, task_id: str, success: bool, seats_found: int, status: str, message: str = "", details: Optional[Dict[str, Any]] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO check_logs (task_id, timestamp, success, seats_found, status, message, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                datetime.now().isoformat(),
                1 if success else 0,
                seats_found,
                status,
                message,
                json.dumps(details) if details else None
            ))
            conn.commit()

    def list_logs(self, task_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if task_id:
                cursor.execute("""
                    SELECT * FROM check_logs WHERE task_id = ? ORDER BY id DESC LIMIT ?
                """, (task_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM check_logs ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def log_notification(self, task_id: str, channel: str, success: bool, title: str, content: str, error_message: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notification_history (task_id, timestamp, channel, success, title, content, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                datetime.now().isoformat(),
                channel,
                1 if success else 0,
                title,
                content,
                error_message
            ))
            conn.commit()

    def list_notification_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notification_history ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as total_tasks FROM tasks")
            total_tasks = cursor.fetchone()["total_tasks"]
            
            cursor.execute("SELECT count(*) as active_tasks FROM tasks WHERE status = 'active'")
            active_tasks = cursor.fetchone()["active_tasks"]

            cursor.execute("SELECT count(*) as total_checks FROM check_logs")
            total_checks = cursor.fetchone()["total_checks"]

            cursor.execute("SELECT count(*) as seats_found FROM check_logs WHERE seats_found > 0")
            seats_found_count = cursor.fetchone()["seats_found"]

            return {
                "total_tasks": total_tasks,
                "active_tasks": active_tasks,
                "total_checks": total_checks,
                "seats_found_count": seats_found_count
            }

    def _row_to_task(self, row: sqlite3.Row) -> TrackingTask:
        d = dict(row)
        d["auto_stop_on_found"] = bool(d.get("auto_stop_on_found", 0))
        return TrackingTask.from_dict(d)
