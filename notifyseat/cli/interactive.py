"""Interactive Terminal Wizard for NotifySeat."""
from datetime import datetime, timedelta
from typing import Optional, List
from notifyseat.core.models import TrackingTask, TransportType, TaskStatus
from notifyseat.providers.registry import registry


def prompt_choice(prompt: str, choices: List[str], default_idx: int = 0) -> int:
    print(f"\n\033[1;36m? {prompt}\033[0m")
    for i, choice in enumerate(choices):
        prefix = "➔" if i == default_idx else " "
        print(f"  {prefix} \033[1;33m[{i+1}]\033[0m {choice}")
    
    while True:
        try:
            val = input(f"\nSelect option [1-{len(choices)}] (default {default_idx+1}): ").strip()
            if not val:
                return default_idx
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                return idx
        except (ValueError, EOFError):
            return default_idx
        print("Invalid selection, please try again.")


def prompt_text(prompt: str, default: str = "") -> str:
    default_str = f" [{default}]" if default else ""
    try:
        val = input(f"\033[1;36m? {prompt}\033[0m{default_str}: ").strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default


def interactive_create_task() -> Optional[TrackingTask]:
    """Guides the user through creating a new tracking task."""
    print("\n" + "=" * 55)
    print("       🚀 \033[1;32mNOTIFYSEAT - NEW ROUTE TRACKER WIZARD\033[0m")
    print("=" * 55)

    # 1. Transport Type
    transport_choices = [
        "🚅 TCDD Train (YHT High Speed & Mainline)",
        "✈️  Flight (Pegasus Airlines / THY / SunExpress)",
        "🚌 Intercity Bus (Pamukkale / Kamil Koç / Metro / Obilet)",
        "🧪 Live Demo / Simulation (Instant Cancellation Test)"
    ]
    t_idx = prompt_choice("Select Transport Mode:", transport_choices, default_idx=0)
    
    t_types = [TransportType.TCDD, TransportType.FLIGHT, TransportType.BUS, TransportType.SIMULATION]
    selected_transport = t_types[t_idx]
    provider = registry.get(selected_transport)

    # Popular routes quick pick
    popular = provider.get_popular_routes()
    pop_labels = [p.get("label", f"{p['origin']} ➔ {p['destination']}") for p in popular]
    pop_labels.append("Custom Route (Type your own stations/cities)...")

    r_idx = prompt_choice("Choose a Route:", pop_labels, default_idx=0)

    if r_idx < len(popular):
        origin = popular[r_idx]["origin"]
        destination = popular[r_idx]["destination"]
    else:
        origin = prompt_text("Enter Departure Station/City/Airport:", default="İstanbul(Söğütlüçeşme)")
        destination = prompt_text("Enter Arrival Station/City/Airport:", default="Ankara Gar")

    # 2. Date
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    date_str = prompt_text("Enter Travel Date (YYYY-MM-DD):", default=tomorrow)

    # 3. Time Filter
    time_choices = [
        "Any Time (Check all journeys of the day)",
        "Morning (05:00 - 12:00)",
        "Afternoon (12:00 - 18:00)",
        "Evening (18:00 - 24:00)",
        "Specific Time (e.g. 08:30)"
    ]
    tm_idx = prompt_choice("Preferred Departure Time Window:", time_choices, default_idx=0)
    time_filter = None
    if tm_idx == 1:
        time_filter = "morning"
    elif tm_idx == 2:
        time_filter = "afternoon"
    elif tm_idx == 3:
        time_filter = "evening"
    elif tm_idx == 4:
        time_filter = prompt_text("Enter specific departure hour (HH:MM):", default="08:30")

    # 4. Check Interval (Fixed to 1 minute / 60 seconds)
    interval_sec = 60

    # 5. Notification Channels
    channels = ["desktop"]

    task = TrackingTask(
        transport_type=selected_transport,
        origin=origin,
        destination=destination,
        date=date_str,
        time_filter=time_filter,
        check_interval_seconds=interval_sec,
        notification_channels=channels,
        status=TaskStatus.ACTIVE
    )

    print("\n\033[1;32m✔ Route tracker configured successfully!\033[0m")
    print(f"  • Name: {task.name}")
    print(f"  • Mode: {task.transport_type.upper()}")
    print(f"  • Date: {task.date}")
    print(f"  • Channels: {', '.join(task.notification_channels)}")
    print(f"  • Interval: Every {task.check_interval_seconds}s\n")
    return task
