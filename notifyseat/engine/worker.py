"""Task Worker: runs availability check for a single task and processes state changes."""
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from notifyseat.core.models import TrackingTask, CheckResult, TaskStatus
from notifyseat.core.database import Database
from notifyseat.core.logger import logger
from notifyseat.notifiers.manager import NotificationManager
from notifyseat.providers.registry import registry


class TaskWorker:
    """Performs checking and notification workflow for a tracking task."""

    def __init__(
        self,
        db: Database,
        notifier_mgr: NotificationManager,
        on_event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
    ):
        self.db = db
        self.notifier_mgr = notifier_mgr
        self.on_event_callback = on_event_callback

    def execute_task(self, task: TrackingTask) -> CheckResult:
        """Runs check for task, handles seat state changes, and sends alerts."""
        provider = registry.get(task.transport_type)
        
        # Emit checking event
        self._emit_event("task_checking", {"task_id": task.id, "name": task.name})

        # Run provider check
        result: CheckResult = provider.check_route(task)
        now_str = datetime.now().isoformat()

        # Log check to database
        self.db.log_check(
            task_id=task.id,
            success=result.success,
            seats_found=result.seats_count,
            status="FOUND" if result.found else ("ERROR" if not result.success else "NO_SEATS"),
            message=result.message,
            details=result.to_dict()
        )

        prev_seats = task.last_found_seats
        new_seats = result.seats_count
        first_service = result.services[0].to_dict() if result.services else None

        # State transition: 0 -> >0 or significant change
        if result.found and (prev_seats == 0 or new_seats != prev_seats):
            logger.info(f"🚨 [SEATS AVAILABLE] Task '{task.name}': {new_seats} seat(s) detected!")

            # Format detailed message
            service_desc = ""
            if result.services:
                s = result.services[0]
                service_desc = f"{s.service_name} at {s.departure_time}"
                if s.class_breakdown:
                    breakdown_str = ", ".join([f"{k}: {v}" for k, v in s.class_breakdown.items() if v > 0])
                    service_desc += f" ({breakdown_str})"

            title = f"Seat Available: {task.origin} ➔ {task.destination}"
            body = f"🎉 Great news! {new_seats} seat(s) found on {service_desc} on {task.date}."
            
            notification_data = {
                "seats_count": new_seats,
                "service_name": result.services[0].service_name if result.services else "Direct Service",
                "departure_time": result.services[0].departure_time if result.services else "",
                "booking_url": result.services[0].booking_url if result.services else "https://ebilet.tcddtasimacilik.gov.tr"
            }

            # Dispatch alerts
            self.notifier_mgr.dispatch(
                title=title,
                message=body,
                task=task,
                data=notification_data
            )

            # Update DB status
            new_status = TaskStatus.FOUND if task.auto_stop_on_found else TaskStatus.ACTIVE
            self.db.update_task_check_state(
                task_id=task.id,
                last_checked=now_str,
                found_seats=new_seats,
                service_info=first_service,
                status=new_status
            )

            self._emit_event("seats_found", {
                "task_id": task.id,
                "name": task.name,
                "seats": new_seats,
                "service": first_service
            })

        else:
            # Update check state without notification
            self.db.update_task_check_state(
                task_id=task.id,
                last_checked=now_str,
                found_seats=new_seats,
                service_info=first_service
            )

            self._emit_event("task_checked", {
                "task_id": task.id,
                "name": task.name,
                "seats": new_seats,
                "found": result.found
            })

        return result

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        if self.on_event_callback:
            try:
                self.on_event_callback(event_type, data)
            except Exception as e:
                logger.warning(f"Error in event callback: {e}")
