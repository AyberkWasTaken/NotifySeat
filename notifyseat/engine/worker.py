"""Task Worker: runs availability check for a single task and processes state changes."""
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
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

        # Build services payload
        services_dict_list = [s.to_dict() for s in result.services]
        last_service_data = {
            "services": services_dict_list,
            "summary": result.message,
            "booking_url": result.services[0].booking_url if result.services else "https://ebilet.tcddtasimacilik.gov.tr"
        } if result.services else None

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

        # State transition: 0 -> >0 or significant seat change
        if result.found and (prev_seats == 0 or new_seats != prev_seats):
            logger.info(f"🚨 [SEATS AVAILABLE] Task '{task.name}': {new_seats} seat(s) detected! -> {result.message}")

            title = f"Seat Available: {task.origin} ➔ {task.destination}"
            body = result.message
            
            first_service = result.services[0] if result.services else None
            notification_data = {
                "seats_count": new_seats,
                "service_name": first_service.service_name if first_service else "Direct Service",
                "departure_time": first_service.departure_time if first_service else "",
                "booking_url": first_service.booking_url if first_service else "https://ebilet.tcddtasimacilik.gov.tr",
                "services": services_dict_list
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
                service_info=last_service_data,
                status=new_status
            )

            self._emit_event("seats_found", {
                "task_id": task.id,
                "name": task.name,
                "seats": new_seats,
                "message": result.message,
                "services": services_dict_list,
                "service_info": last_service_data
            })

        else:
            # Update check state without notification
            self.db.update_task_check_state(
                task_id=task.id,
                last_checked=now_str,
                found_seats=new_seats,
                service_info=last_service_data
            )

            self._emit_event("task_checked", {
                "task_id": task.id,
                "name": task.name,
                "seats": new_seats,
                "found": result.found,
                "message": result.message,
                "services": services_dict_list
            })

        return result

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        if self.on_event_callback:
            try:
                self.on_event_callback(event_type, data)
            except Exception as e:
                logger.warning(f"Error in event callback: {e}")
