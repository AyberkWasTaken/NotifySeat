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
from notifyseat.cli.interactive import interactive_create_task, interactive_config

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
[/bold cyan][dim]Local-First Transport Seat & Cancellation Notifier[/dim]
"""
        console.print(banner)
    else:
        print("\n=== NotifySeat - Local Seat Availability Notifier ===\n")


def cmd_list(db: Database):
    tasks = db.list_tasks()
    if not tasks:
        print("\nNo tracking routes found. Create one with: python3 main.py track\n")
        return

    if HAS_RICH and console:
        console.print()
        console.print(Panel("[bold cyan]🚆 Monitored Transport Routes[/bold cyan]", expand=True, border_style="cyan"))
        table = Table(show_header=True, header_style="bold magenta", border_style="dim white")
        table.add_column("ID", justify="center", style="bold cyan", width=6)
        table.add_column("Route", justify="left", style="bold white")
        table.add_column("Date", justify="center", style="bold yellow")
        table.add_column("Window", justify="center", style="green")
        table.add_column("Radar Status", justify="center")
        table.add_column("Seats Available", justify="center")
        table.add_column("Last Check", justify="center", style="dim")

        for t in tasks:
            status_badge = {
                TaskStatus.ACTIVE: "[bold green]🟢 ACTIVE[/bold green]",
                TaskStatus.PAUSED: "[bold yellow]⏸ PAUSED[/bold yellow]",
                TaskStatus.FOUND: "[bold green]✔ FOUND[/bold green]",
                TaskStatus.ERROR: "[bold red]✖ ERROR[/bold red]"
            }.get(t.status, str(t.status))

            seats_display = f"[bold green]🟢 {t.last_found_seats} Seat{'s' if t.last_found_seats > 1 else ''}[/bold green]" if t.last_found_seats > 0 else "[bold red]🔴 Sold Out[/bold red]"
            window_label = t.time_filter.title() if t.time_filter else "All Day"
            last_checked = t.last_checked_at.split("T")[-1][:8] if t.last_checked_at else "Pending"

            table.add_row(
                str(t.id),
                f"{t.origin} ➔ {t.destination}",
                t.display_date,
                window_label,
                status_badge,
                seats_display,
                last_checked
            )
        console.print(table)
        console.print("[dim]Commands: 'notifyseat check <id>' | 'notifyseat delete <id>' | 'notifyseat pause <id>'[/dim]\n")
    else:
        print("\n--- Monitored Routes ---")
        for t in tasks:
            print(f"[{t.id}] {t.origin} -> {t.destination} ({t.display_date}) | Status: {t.status} | Seats: {t.last_found_seats}")
        print()


def cmd_track(db: Database, args: argparse.Namespace):
    if args.interactive or not (args.origin and args.destination):
        task = interactive_create_task()
        if task:
            db.create_task(task)
            print(f"✔ Task [{task.id}] saved to database! Run 'notifyseat run' or launch 'notifyseat gui' to monitor.")
    else:
        channels = args.channels.split(",") if args.channels else ["desktop"]
        task = TrackingTask(
            transport_type=TransportType.from_str(args.transport),
            origin=args.origin,
            destination=args.destination,
            date=args.date or (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y"),
            time_filter=args.time,
            check_interval_seconds=args.interval or 300,
            notification_channels=channels,
            status=TaskStatus.ACTIVE
        )
        db.create_task(task)
        print(f"✔ Created tracking task [{task.id}]: {task.name}")


def render_track_check_table(task: TrackingTask, result):
    window_label = task.time_filter.title() if task.time_filter else "All Day"
    title_text = (
        f"[bold cyan]🚆 Route:[/bold cyan] [bold white]{task.origin} ➔ {task.destination}[/bold white]   "
        f"[bold cyan]📅 Date:[/bold cyan] [bold yellow]{task.display_date}[/bold yellow]   "
        f"[bold cyan]🕒 Window:[/bold cyan] [bold green]{window_label}[/bold green]   "
        f"[bold cyan]🆔 ID:[/bold cyan] [dim]{task.id}[/dim]"
    )
    if HAS_RICH and console:
        console.print()
        console.print(Panel(title_text, expand=True, border_style="cyan"))

        if result.services:
            table = Table(show_header=True, header_style="bold magenta", border_style="dim white")
            table.add_column("Departure", justify="center", style="bold yellow")
            table.add_column("Train No", justify="center", style="bold cyan")
            table.add_column("Status", justify="center")
            table.add_column("Business", justify="center")
            table.add_column("Ekonomi", justify="center")
            table.add_column("Min Price", justify="center", style="bold green")

            for s in result.services:
                dep = s.departure_time or "??"
                arr = s.arrival_time or ""
                dep_str = f"{dep} ➔ {arr}" if arr else dep
                train_no = s.service_id or s.service_name.split()[0]

                seats = s.total_available_seats
                bd = s.class_breakdown
                price = s.price
                curr = s.currency or "TRY"

                bus_cnt = bd.get("Business", 0)
                eko_cnt = bd.get("Ekonomi", 0)

                if seats > 0:
                    status_cell = f"[bold green]🟢 {seats} Seat{'s' if seats > 1 else ''}[/bold green]"
                    bus_cell = f"[green]{bus_cnt}[/green]" if bus_cnt > 0 else "[dim]0[/dim]"
                    eko_cell = f"[bold green]{eko_cnt}[/bold green]" if eko_cnt > 0 else "[dim]0[/dim]"
                    price_cell = f"{price:.0f} {curr}" if price else "-"
                else:
                    status_cell = "[bold red]🔴 Sold Out[/bold red]"
                    bus_cell = "[dim red]0[/dim red]"
                    eko_cell = "[dim red]0[/dim red]"
                    price_cell = "[dim]-[/dim]"

                table.add_row(dep_str, train_no, status_cell, bus_cell, eko_cell, price_cell)

            console.print(table)
            if result.found:
                console.print(f"[bold green]✔ Status: {result.seats_count} total available seat(s) detected across routes.[/bold green]\n")
            else:
                console.print(f"[yellow]● Status: All routes currently Sold Out. Monitoring for cancellations...[/yellow]\n")
        else:
            if result.found:
                console.print(f"[bold green]✔ Status: {result.seats_count} seat(s) available.[/bold green]\n")
            else:
                console.print(f"[yellow]● Status: Sold Out. Monitoring...[/yellow]\n")
    else:
        print(f"\n--- [{task.origin} -> {task.destination} ({task.date})] ---")
        print(f"Seats: {result.seats_count} | Found: {result.found}")


def cmd_check_now(db: Database, config_mgr: ConfigManager, task_id: Optional[str] = None):
    if task_id:
        tasks = [db.get_task(task_id)]
        if not tasks[0]:
            print(f"✖ Task [{task_id}] not found in database.")
            return
    else:
        tasks = db.list_tasks(status=TaskStatus.ACTIVE) or db.list_tasks()
        if not tasks:
            print("✖ No tasks found in database. Create one with: python3 main.py track")
            return

    cfg = config_mgr.get()
    notifier_mgr = NotificationManager(cfg, db)
    scheduler = EngineScheduler(db, cfg, notifier_mgr)

    for task in tasks:
        result = scheduler.worker.execute_task(task)
        render_track_check_table(task, result)


def cmd_run(db: Database, config_mgr: ConfigManager, args: argparse.Namespace):
    print_banner()
    cfg = config_mgr.get()
    notifier_mgr = NotificationManager(cfg, db)
    scheduler = EngineScheduler(db, cfg, notifier_mgr)

    tasks = db.list_tasks(status=TaskStatus.ACTIVE)
    if not tasks:
        print("⚠️ No active tasks in database! Adding a default tracker for you...")
        demo_task = TrackingTask(
            name="İstanbul -> Eskişehir Tracker",
            transport_type=TransportType.TCDD,
            origin="İstanbul(Söğütlüçeşme)",
            destination="Eskişehir",
            date=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            time_filter="evening",
            check_interval_seconds=60,
            notification_channels=["desktop"]
        )
        db.create_task(demo_task)
        tasks = [demo_task]

    print(f"\n[bold green]Starting NotifySeat Engine... Monitoring {len(tasks)} active route(s) (1-minute cycle)[/bold green]" if HAS_RICH else f"Starting NotifySeat Engine for {len(tasks)} tasks...")
    print("Press Ctrl+C at any time to exit gracefully.\n")

    def on_event(event_type: str, data: dict):
        task_obj = data.get("task")
        result_obj = data.get("result")
        
        if task_obj and result_obj:
            render_track_check_table(task_obj, result_obj)
        else:
            ts = datetime.now().strftime("%H:%M:%S")
            msg = data.get("message") or f"Checked {data.get('name')}: {data.get('seats', 0)} seats."
            print(f"[{ts}] {msg}")

        if event_type == "seats_found":
            if HAS_RICH:
                console.print(Panel(
                    f"[bold green]🚨 CANCELLATION OPENING DETECTED![/bold green]\n\n"
                    f"Route: [bold white]{data.get('name')}[/bold white]\n"
                    f"Seats Available: [bold yellow]{data.get('seats')}[/bold yellow]\n\n"
                    f"[dim]Notification dispatched via desktop chime & active channels.[/dim]",
                    title="🎉 INSTANT ALERT",
                    border_style="green"
                ))

    scheduler.subscribe_events(on_event)
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        scheduler.stop()
        print("✔ NotifySeat stopped.")


def cmd_config(config_mgr: ConfigManager):
    interactive_config(config_mgr)


def cmd_test_notify(config_mgr: ConfigManager, channel: Optional[str] = None):
    cfg = config_mgr.get()
    mgr = NotificationManager(cfg)
    
    if channel:
        print(f"\nTesting notification channel: '{channel}'...")
        success = mgr.test_channel(channel)
        if success:
            print(f"\033[1;32m✔ [{channel.upper()}] Test notification was SUCCESSFUL!\033[0m\n")
        else:
            print(f"\033[1;31m✖ [{channel.upper()}] Test notification failed. Check credentials with 'python3 main.py config'.\033[0m\n")
    else:
        print("\n\033[1;36m==================================================\033[0m")
        print("\033[1;36m        ⚡ Testing Notification Channels          \033[0m")
        print("\033[1;36m==================================================\033[0m\n")
        results = mgr.test_all()
        for ch, data in results.items():
            label = data["label"]
            if data["enabled"]:
                if data["success"]:
                    print(f"  \033[1;32m✔ [{ch.upper()}]\033[0m {label}: \033[1;32mSUCCESSFUL (Delivered!)\033[0m")
                else:
                    print(f"  \033[1;31m✖ [{ch.upper()}]\033[0m {label}: \033[1;31mFAILED (Check credentials via 'python3 main.py config')\033[0m")
            else:
                print(f"  \033[1;30m⚪ [{ch.upper()}]\033[0m {label}: \033[2mDisabled (Run 'python3 main.py config' to enable)\033[0m")
        print()


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
    track_p.add_argument("-t", "--transport", default="tcdd", choices=["tcdd", "flight", "bus"], help="Transport type")
    track_p.add_argument("--from", dest="origin", help="Departure station/airport/city")
    track_p.add_argument("--to", dest="destination", help="Arrival station/airport/city")
    track_p.add_argument("--date", help="Travel date (YYYY-MM-DD)")
    track_p.add_argument("--time", help="Time filter (e.g. morning, afternoon, evening, all)")
    track_p.add_argument("--channels", default="desktop", help="Comma-separated channels: desktop,email,whatsapp")

    # check
    chk_p = subparsers.add_parser("check", help="Trigger an immediate live check for a task (or all active tasks)")
    chk_p.add_argument("task_id", nargs="?", default=None, help="Task ID to check (optional, checks all active if omitted)")

    # run
    subparsers.add_parser("run", help="Start monitoring engine in foreground")
    subparsers.add_parser("start", help="Alias for run")

    # config / notify-setup
    subparsers.add_parser("config", help="Configure Email and WhatsApp alerts (auto-opens browser)")
    subparsers.add_parser("notify-setup", help="Alias for config")

    # gui
    gui_p = subparsers.add_parser("gui", help="Launch the local Web GUI dashboard")
    gui_p.add_argument("--host", default="127.0.0.1", help="Host address (default 127.0.0.1)")
    gui_p.add_argument("--port", type=int, default=8080, help="Port number (default 8080)")

    # test-notify
    test_p = subparsers.add_parser("test-notify", help="Test active notification channels")
    test_p.add_argument("channel", nargs="?", default=None, choices=["desktop", "email", "whatsapp", "telegram", "discord"], help="Optional specific channel to test")

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
        print("  notifyseat check [id]    ➔ Trigger immediate live check (or check all)")
        print("  notifyseat list          ➔ View all configured routes")
        print("  notifyseat config        ➔ Setup WhatsApp & Email alerts (auto-opens browser)")
        print("  notifyseat test-notify   ➔ Test WhatsApp, Email, Desktop alerts")
        print("  notifyseat gui           ➔ Launch the local Web GUI dashboard")
        print("  notifyseat delete <id>   ➔ Delete a task")
        print("  notifyseat pause <id>    ➔ Pause monitoring for a task")
        print("  notifyseat resume <id>   ➔ Resume monitoring for a task\n")
        return

    try:
        if args.command == "list":
            cmd_list(db)
        elif args.command == "track":
            cmd_track(db, args)
        elif args.command == "check":
            cmd_check_now(db, config_mgr, args.task_id)
        elif args.command in ("run", "start"):
            cmd_run(db, config_mgr, args)
        elif args.command in ("config", "notify-setup"):
            cmd_config(config_mgr)
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
    except KeyboardInterrupt:
        print("\n\n\033[2mOperation cancelled.\033[0m\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
