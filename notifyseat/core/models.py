"""Core data models for NotifySeat."""
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
import json
import uuid


class TransportType(str, Enum):
    TCDD = "tcdd"
    FLIGHT = "flight"
    BUS = "bus"
    SIMULATION = "simulation"

    @classmethod
    def from_str(cls, val: str):
        val = val.lower().strip()
        for member in cls:
            if member.value == val:
                return member
        return cls.SIMULATION


class TaskStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    FOUND = "found"
    COMPLETED = "completed"
    ERROR = "error"


class NotificationChannel(str, Enum):
    DESKTOP = "desktop"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"


@dataclass
class ServiceInfo:
    """Represents a specific train, flight, or bus journey."""
    service_id: str
    service_name: str
    departure_time: str
    arrival_time: str
    origin: str
    destination: str
    date: str
    total_available_seats: int
    class_breakdown: Dict[str, int] = field(default_factory=dict)
    car_breakdown: List[Dict[str, Any]] = field(default_factory=list)
    price: Optional[float] = None
    currency: str = "TRY"
    booking_url: Optional[str] = None
    operator: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def format_display_date(date_str: str) -> str:
    """Converts YYYY-MM-DD to DD-MM-YYYY (day first, month in the middle) for display."""
    if not date_str:
        return ""
    try:
        clean = date_str.strip().replace(".", "-").replace("/", "-")
        parts = clean.split("-")
        if len(parts) == 3:
            if len(parts[0]) == 4:  # YYYY-MM-DD -> DD-MM-YYYY
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
            elif len(parts[2]) == 4:  # Already DD-MM-YYYY
                return f"{parts[0]}-{parts[1]}-{parts[2]}"
    except Exception:
        pass
    return date_str


def normalize_date_input(date_str: str) -> str:
    """Normalizes any date format (DD-MM-YYYY, DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD) to ISO YYYY-MM-DD."""
    if not date_str:
        return ""
    try:
        clean = date_str.strip().replace(".", "-").replace("/", "-")
        parts = clean.split("-")
        if len(parts) == 3:
            if len(parts[0]) == 4:  # YYYY-MM-DD
                return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
            elif len(parts[2]) == 4:  # DD-MM-YYYY -> YYYY-MM-DD
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    except Exception:
        pass
    return date_str


@dataclass
class TrackingTask:
    """Represents a route tracking task saved by the user."""
    id: str = ""
    name: str = ""
    transport_type: TransportType = TransportType.TCDD
    origin: str = ""
    origin_id: Optional[str] = None
    destination: str = ""
    destination_id: Optional[str] = None
    date: str = ""  # YYYY-MM-DD
    time_filter: Optional[str] = None  # e.g., "08:00-14:00" or specific hour "09:15"
    min_seats: int = 1
    seat_class: str = "ANY"  # ANY, ECONOMY, BUSINESS, PULMAN, YATAKLI
    check_interval_seconds: int = 90
    notification_channels: List[str] = field(default_factory=lambda: ["desktop"])
    status: TaskStatus = TaskStatus.ACTIVE
    last_checked_at: Optional[str] = None
    last_found_seats: int = 0
    last_service_info: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    auto_stop_on_found: bool = False

    @property
    def display_date(self) -> str:
        return format_display_date(self.date)

    def __post_init__(self):
        if self.date:
            self.date = normalize_date_input(self.date)
        if isinstance(self.transport_type, str):
            self.transport_type = TransportType.from_str(self.transport_type)
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)
        if not self.name:
            self.name = f"{self.origin} -> {self.destination} ({self.display_date})"

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["transport_type"] = self.transport_type.value
        res["status"] = self.status.value
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackingTask":
        clean_data = dict(data)
        if "transport_type" in clean_data:
            clean_data["transport_type"] = TransportType.from_str(clean_data["transport_type"])
        if "status" in clean_data:
            clean_data["status"] = TaskStatus(clean_data["status"])
        if isinstance(clean_data.get("notification_channels"), str):
            try:
                clean_data["notification_channels"] = json.loads(clean_data["notification_channels"])
            except Exception:
                clean_data["notification_channels"] = ["desktop"]
        if isinstance(clean_data.get("last_service_info"), str) and clean_data["last_service_info"]:
            try:
                clean_data["last_service_info"] = json.loads(clean_data["last_service_info"])
            except Exception:
                clean_data["last_service_info"] = None
        return cls(**clean_data)


@dataclass
class CheckResult:
    """Represents the output of a single check run on a route."""
    task_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True
    found: bool = False
    seats_count: int = 0
    services: List[ServiceInfo] = field(default_factory=list)
    message: str = ""
    error_message: Optional[str] = None
    rate_limited: bool = False
    backoff_seconds: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "success": self.success,
            "found": self.found,
            "seats_count": self.seats_count,
            "services": [s.to_dict() for s in self.services],
            "message": self.message,
            "error_message": self.error_message,
            "rate_limited": self.rate_limited,
            "backoff_seconds": self.backoff_seconds,
        }
