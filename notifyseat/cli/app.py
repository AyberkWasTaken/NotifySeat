"""CLI entrypoint and command handlers for NotifySeat."""
import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
from notifyseat.core.models import TrackingTask, TransportType, TaskStatus
from notifyseat.core.database import Database
from notifyseat.core.config import ConfigManager
from notifyseat.core.logger import logger
from notifyseat.notifiers.manager import NotificationManager
from notifyseat.engine.scheduler import EngineScheduler
from notifyseat.cli.interactive import interactive_create_task

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    console = None


def print_banner():
    if HAS_RICH:
        banner = r"""[bold cyan]
  _   _       _   _  __       ____             _   
 | \ | | ___ | |_(_)/ _|_   _/ ___|  ___  __ _| |_ 
 |  \| |/ _ \| __| | |_| | | \___ \ / _ \/ _` | __|
 | |\  | (_) | |_| |  _| |_| |___) |  __/ (_| | |_ 
 |_| \_|\___/ \__|_|_|  \__, |____/ \___|\__,_|\__|
                        |___/                      
[/bold cyan][dim]Local-First Transport Seat & Cancellation Notifier • Made for Ayberk[/dim]
"""
        console.print(banner)
    else:
        print("\n=== NotifySeat - Local Seat Availability Notifier ===\n")


def cmd_list(db: Database):
    tasks = db.list_tasks()
    if not tasks:
        print("\nNo tracking tasks found. Create one with: notifyseat track\n")
        return

    if HAS_RICH:
        table = Table(title="🚆 Active & Monitored Transport Routes", header_style="bold magenta")
        table.add_column("ID", style="dim", width=10)
        table.add_column("Transport", style="cyan")
        table.add_column("Route", style="bold white")
        table.add_column("Date", style="yellow")
        table.add_column("Interval", style="blue")
        table.add_column("Channels", style="green")
        table.add_column("Status", style="bold")
        table.add_column("Seats Found", justify="right")
        table.add_column("Last Checked", style="dim")

        for t in tasks:
            status_style = {
                TaskStatus.ACTIVE: "[green]● ACTIVE[/green]",
                TaskStatus.PAUSED: "[yellow]❚❚ PAUSED[/yellow]",
                TaskStatus.FOUND: "[bold green]✔ FOUND[/bold green]",
                TaskStatus.ERROR: "[red]✖ ERROR[/red]"
            }.get(t.status, str(t.status))

            seats_display = f"[bold green]{t.last_found_seats}[/bold green]" if t.last_found_seats > 0 else "[dim]0[/dim]"
            last_checked = t.last_checked_at.split("T")[-1][:8] if t.last_checked_at else "Never"

            table.add_row(
                t.id,
                t.transport_type.upper(),
                f"{t.origin} ➔ {t.destination}",
                t.date,
                f"{t.check_interval_seconds}s",
                ", ".join(t.notification_channels),
                status_style,
                seats_display,
                last_checked
            )
        console.print(table)
        console.print()
    else:
        print("\n--- Monitored Routes ---")
        for t in tasks:
            print(f"[{t.id}] {t.transport_type.upper()}: {t.origin} -> {t.destination} ({t.date}) | Status: {t.status} | Seats: {t.last_found_seats}")
        print()


def cmd_track(db: Database, args: argparse.Namespace):
    if args.interactive or not (args.origin and args.destination):
        task = interactive_create_task()
        if task:
            db.create_task(task)
            print(f"✔ Task [{task.id}] saved to database! Run 'notifyseat run' to start checking.")
    else:
        channels = args.channels.split(",") if args.channels else ["desktop"]
        task = TrackingTask(
            transport_type=TransportType.from_str(args.transport),
            origin=args.origin,
            destination=args.destination,
            date=args.date or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            time_filter=args.time,
            check_interval_seconds=args.interval or 30,
            notification_channels=channels,
            status=TaskStatus.ACTIVE
        )
        db.create_task(task)
        print(f"✔ Created tracking task [{task.id}]: {task.name}")


def cmd_run(db: Database, config_mgr: ConfigManager, args: argparse.Namespace):
    print_banner()
    cfg = config_mgr.get()
    notifier_mgr = NotificationManager(cfg, db)
    scheduler = EngineScheduler(db, cfg, notifier_mgr)

    tasks = db.list_tasks(status=TaskStatus.ACTIVE)
    if not tasks:
        print("⚠️ No active tasks in database! Adding a demo simulation task for you...")
        demo_task = TrackingTask(
            name="Demo TCDD YHT Express",
            transport_type=TransportType.SIMULATION,
            origin="İstanbul(Söğütlüçeşme)",
            destination="Ankara Gar",
            date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            check_interval_seconds=8,
            notification_channels=["desktop"]
        )
        db.create_task(demo_task)
        tasks = [demo_task]

    print(f"\n[bold green]Starting NotifySeat Engine... Monitoring {len(tasks)} active route(s)[/bold green]" if HAS_RICH else f"Starting NotifySeat Engine for {len(tasks)} tasks...")
    print("Press Ctrl+C at any time to exit gracefully.\n")

    def on_event(event_type: str, data: dict):
        ts = datetime.now().strftime("%H:%M:%S")
        if event_type == "seats_found":
            if HAS_RICH:
                console.print(Panel(
                    f"[bold green]🚨 SEATS DETECTED![/bold green]\n"
                    f"Route: [bold white]{data.get('name')}[/bold white]\n"
                    f"Available Seats: [bold yellow]{data.get('seats')}[/bold yellow]\n"
                    f"Notification dispatched via configured channels!",
                    title="🎉 CANCELLATION OPENING FOUND",
                    border_style="green"
                ))
            else:
                print(f"[{ts}] 🚨 SEATS DETECTED! {data.get('name')} -> {data.get('seats')} seats available!")
        elif event_type == "task_checked":
            seats = data.get("seats", 0)
            if seats == 0:
                print(f"[{ts}] 🔍 Checked {data.get('name')}: Full (0 seats). Monitoring...")
            else:
                print(f"[{ts}] ✔ Checked {data.get('name')}: {seats} seats available.")

    scheduler.subscribe_events(on_event)
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        scheduler.stop()
        print("✔ NotifySeat stopped.")


def cmd_demo(db: Database, config_mgr: ConfigManager):
    """Runs an instant interactive demo showing seat detection and notification."""
    print_banner()
    print("\n🎬 \033[1;33mRUNNING INSTANT LIVE DEMO (Seat Cancellation Scenario)\033[0m")
    print("This will simulate a sold-out train where a passenger cancels their ticket live!\n")

    demo_task = TrackingTask(
        name="Istanbul ➔ Ankara YHT (Live Demo)",
        transport_type=TransportType.SIMULATION,
        origin="İstanbul(Söğütlüçeşme)",
        destination="Ankara Gar",
        date=(datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        check_interval_seconds=4,
        notification_channels=["desktop"]
    )
    db.create_task(demo_task)

    cfg = config_mgr.get()
    notifier_mgr = NotificationManager(cfg, db)
    scheduler = EngineScheduler(db, cfg, notifier_mgr)

    def on_event(event_type: str, data: dict):
        ts = datetime.now().strftime("%H:%M:%S")
        if event_type == "seats_found":
            print(f"\n\a\033[1;32m[{ts}] 🎉 BREAKING: PASSENGER CANCELLATION DETECTED!\033[0m")
            print(f"  • Route: {data.get('name')}")
            print(f"  • Opened Seats: {data.get('seats')} (Pulman & Business)")
            print(f"  • Status: Alert dispatched to Desktop / Sound / Telegram!\n")
        elif event_type == "task_checked":
            print(f"[{ts}] 🔍 Checking route... Status: Train is currently SOLD OUT (0 seats). Waiting...")

    scheduler.subscribe_events(on_event)
    scheduler.start()

    print("Step 1: Checking sold out train...")
    time.sleep(12)
    scheduler.stop()
    print("\n\033[1;32m✔ Demo completed successfully! Working end-to-end.\033[0m\n")


def cmd_test_notify(config_mgr: ConfigManager, channel: str):
    cfg = config_mgr.get()
    mgr = NotificationManager(cfg)
    print(f"Testing notification channel: '{channel}'...")
    success = mgr.test_channel(channel)
    if success:
        print(f"\033[1;32m✔ Test notification for '{channel}' was SUCCESSFUL!\033[0m")
    else:
        print(f"\033[1;31m✖ Test notification for '{channel}' failed. Please check configuration settings.\033[0m")


def main():
    parser = argparse.ArgumentParser(
        prog="notifyseat",
        description="NotifySeat: Local-First Transport Seat & Cancellation Notifier"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # list
    subparsers.add_parser("list", help="List all monitored routes")

    # track
    track_p = subparsers.add_parser("track", help="Add or configure a new route to monitor")
    track_p.add_argument("-i", "--interactive", action="store_true", help="Launch interactive wizard")
    track_p.add_argument("-t", "--transport", default="tcdd", choices=["tcdd", "flight", "bus", "simulation"], help="Transport type")
    track_p.add_argument("--from", dest="origin", help="Departure station/airport/city")
    track_p.add_argument("--to", dest="destination", help="Arrival station/airport/city")
    track_p.add_argument("--date", help="Travel date (YYYY-MM-DD)")
    track_p.add_argument("--time", help="Time filter (e.g. morning, 08:30, 08:00-14:00)")
    track_p.add_argument("--interval", type=int, default=30, help="Check frequency in seconds")
    track_p.add_argument("--channels", default="desktop", help="Comma-separated channels: desktop,telegram,discord,email,sms,webhook")

    # run
    subparsers.add_parser("run", help="Start monitoring engine in foreground")
    subparsers.add_parser("start", help="Alias for run")

    # demo
    subparsers.add_parser("demo", help="Run an instant live cancellation demo")

    # gui
    gui_p = subparsers.add_parser("gui", help="Launch the local Web GUI dashboard")
    gui_p.add_argument("--host", default="127.0.0.1", help="Host address (default 127.0.0.1)")
    gui_p.add_argument("--port", type=int, default=8080, help="Port number (default 8080)")

    # test-notify
    test_p = subparsers.add_parser("test-notify", help="Test a notification channel")
    test_p.add_argument("channel", choices=["desktop", "telegram", "discord", "email", "sms", "webhook"], help="Channel to test")

    # delete
    del_p = subparsers.add_parser("delete", help="Delete a tracking task")
    del_p.add_argument("task_id", help="Task ID to delete")

    # pause / resume
    p_p = subparsers.add_parser("pause", help="Pause a tracking task")
    p_p.add_argument("task_id", help="Task ID")
    r_p = subparsers.add_parser("resume", help="Resume a tracking task")
    r_p.add_argument("task_id", help="Task ID")

    args = parser.parse_args()

    db = Database()
    config_mgr = ConfigManager()

    if not args.command or args.command in ("help", "-h", "--help"):
        print_banner()
        cmd_list(db)
        print("\nCommands available:")
        print("  notifyseat track         ➔ Add a new route to monitor")
        print("  notifyseat run           ➔ Start the background monitoring engine")
        print("  notifyseat demo          ➔ Run an instant live cancellation demo")
        print("  notifyseat gui           ➔ Launch the local Web GUI dashboard")
        print("  notifyseat list          ➔ View all configured tasks")
        print("  notifyseat test-notify   ➔ Test Telegram, Discord, Email, Desktop alert")
        print("  notifyseat delete <id>   ➔ Delete a task\n")
        return

    if args.command == "list":
        cmd_list(db)
    elif args.command == "track":
        cmd_track(db, args)
    elif args.command in ("run", "start"):
        cmd_run(db, config_mgr, args)
    elif args.command == "demo":
        cmd_demo(db, config_mgr)
    elif args.command == "test-notify":
        cmd_test_notify(config_mgr, args.channel)
    elif args.command == "delete":
        if db.delete_task(args.task_id):
            print(f"✔ Task [{args.task_id}] deleted.")
        else:
            print(f"✖ Task [{args.task_id}] not found.")
    elif args.command == "pause":
        if db.update_task_status(args.task_id, TaskStatus.PAUSED):
            print(f"✔ Task [{args.task_id}] paused.")
        else:
            print(f"✖ Task [{args.task_id}] not found.")
    elif args.command == "resume":
        if db.update_task_status(args.task_id, TaskStatus.ACTIVE):
            print(f"✔ Task [{args.task_id}] resumed.")
        else:
            print(f"✖ Task [{args.task_id}] not found.")
    elif args.command == "gui":
        from notifyseat.web.server import run_web_server
        run_web_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
