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

        # State transition: Only notify when a sold-out route gets seats (0 -> >0)
        # or when new cancellation seats open up (new_seats > prev_seats).
        # Never send repeated alerts if seats stay the same.
        should_notify = result.found and (prev_seats == 0 or new_seats > prev_seats)

        if should_notify:
            open_services = [s for s in result.services if s.total_available_seats > 0]
            first_s = open_services[0] if open_services else (result.services[0] if result.services else None)
            
            if open_services:
                summary_lines = []
                for s in open_services:
                    cls_str = ", ".join([f"{cnt} {cls}" for cls, cnt in s.class_breakdown.items() if cnt > 0])
                    summary_lines.append(f"• {s.departure_time} ({s.service_name}): {s.total_available_seats} seat(s) [{cls_str}]")
                details_text = "\n".join(summary_lines)
            else:
                details_text = f"{new_seats} seat(s) available."

            title = f"🎉 Seat Opening: {task.origin} ➔ {task.destination}"
            body = (
                f"🚨 CANCELLATION DETECTED!\n"
                f"🚆 Route: {task.origin} ➔ {task.destination}\n"
                f"📅 Date: {task.display_date}\n\n"
                f"💺 Available Seats:\n{details_text}\n\n"
                f"🔗 Book Immediately: https://ebilet.tcddtasimacilik.gov.tr"
            )

            notification_data = {
                "seats_count": new_seats,
                "service_name": first_s.service_name if first_s else "Direct Service",
                "departure_time": first_s.departure_time if first_s else "",
                "booking_url": "https://ebilet.tcddtasimacilik.gov.tr",
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
                "task": task,
                "result": result,
                "name": task.name,
                "seats": new_seats,
                "message": body,
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
                "task": task,
                "result": result,
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
