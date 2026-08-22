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
            print(f"✔ Task [{task.id}] saved to database! Run 'notifyseat run' or launch 'notifyseat gui' to monitor.")
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


def render_track_check_table(task: TrackingTask, result):
    window_label = task.time_filter.title() if task.time_filter else "All Day"
    title_text = (
        f"[bold cyan]🚆 Route:[/bold cyan] [bold white]{task.origin} ➔ {task.destination}[/bold white]   "
        f"[bold cyan]📅 Date:[/bold cyan] [bold yellow]{task.date}[/bold yellow]   "
        f"[bold cyan]🕒 Window:[/bold cyan] [bold green]{window_label}[/bold green]   "
        f"[bold cyan]🆔 ID:[/bold cyan] [dim]{task.id}[/dim]"
    )
    if HAS_RICH and console:
        console.print()
        console.print(Panel(title_text, expand=True, border_style="cyan"))

        if result.services:
            table = Table(show_header=True, header_style="bold magenta", border_style="dim white", expand=True)
            table.add_column("Departure", justify="center", style="bold yellow", width=14)
            table.add_column("Train & Service", justify="left", style="white", min_width=25)
            table.add_column("Status", justify="center", width=14)
            table.add_column("Business", justify="center", width=10)
            table.add_column("Ekonomi", justify="center", width=10)
            table.add_column("Özel / Engelli", justify="center", width=15)
            table.add_column("Min Price", justify="center", style="bold green", width=12)

            for s in result.services:
                dep = s.departure_time or "??"
                arr = s.arrival_time or ""
                dep_str = f"{dep} ➔ {arr}" if arr else dep
                name = s.service_name
                seats = s.total_available_seats
                bd = s.class_breakdown
                price = s.price
                curr = s.currency or "TRY"

                bus_cnt = bd.get("Business", 0)
                eko_cnt = bd.get("Ekonomi", 0)
                ozel_cnt = bd.get("Engelli/Özel", bd.get("Loca", bd.get("Yataklı", 0)))

                if seats > 0:
                    status_cell = f"[bold green]🟢 {seats} Seat{'s' if seats > 1 else ''}[/bold green]"
                    bus_cell = f"[green]{bus_cnt}[/green]" if bus_cnt > 0 else "[dim]0[/dim]"
                    eko_cell = f"[bold green]{eko_cnt}[/bold green]" if eko_cnt > 0 else "[dim]0[/dim]"
                    ozel_cell = f"[green]{ozel_cnt}[/green]" if ozel_cnt > 0 else "[dim]0[/dim]"
                    price_cell = f"{price:.0f} {curr}" if price else "-"
                else:
                    status_cell = "[bold red]🔴 Sold Out[/bold red]"
                    bus_cell = "[dim red]0[/dim red]"
                    eko_cell = "[dim red]0[/dim red]"
                    ozel_cell = "[dim red]0[/dim red]"
                    price_cell = "[dim]-[/dim]"

                table.add_row(dep_str, name, status_cell, bus_cell, eko_cell, ozel_cell, price_cell)

            console.print(table)
            if result.found:
                console.print(f"[bold green]✔ {result.message}[/bold green]")
            else:
                console.print(f"[yellow]{result.message}[/yellow]")
            console.print()
        else:
            if result.found:
                console.print(f"[bold green]{result.message}[/bold green]\n")
            else:
                console.print(f"[yellow]{result.message}[/yellow]\n")
    else:
        print(f"\n--- [{task.origin} -> {task.destination} ({task.date})] ---")
        print(result.message)


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
        print("⚠️ No active tasks in database! Adding a demo simulation task for you...")
        demo_task = TrackingTask(
            name="Demo TCDD YHT Express",
            transport_type=TransportType.SIMULATION,
            origin="İstanbul(Söğütlüçeşme)",
            destination="Eskişehir",
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
            msg = data.get("message") or f"Found {data.get('seats')} seats on {data.get('name')}!"
            if HAS_RICH:
                console.print(Panel(
                    f"[bold green]🚨 SEATS DETECTED![/bold green]\n\n"
                    f"{msg}\n\n"
                    f"[dim]Notification dispatched via configured channels.[/dim]",
                    title="🎉 CANCELLATION OPENING FOUND",
                    border_style="green"
                ))
            else:
                print(f"\n\a[{ts}] 🚨 SEATS DETECTED! {msg}\n")
        elif event_type == "task_checked":
            msg = data.get("message") or f"Checked {data.get('name')}: {data.get('seats', 0)} seats."
            print(f"[{ts}] {msg}")

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
        name="İstanbul(Söğütlüçeşme) ➔ Eskişehir YHT (Live Demo)",
        transport_type=TransportType.SIMULATION,
        origin="İstanbul(Söğütlüçeşme)",
        destination="Eskişehir",
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
            print(f"  • {data.get('message')}")
            print(f"  • Status: Alert dispatched to Desktop / Audio Chime / Telegram!\n")
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


def cmd_connect_tcdd(config_mgr: ConfigManager):
    print("\n🌐 Launching interactive browser to connect TCDD live session...")
    print("👉 Please select your route and click 'Ara' (Search) in the browser window.")
    print("👉 NotifySeat will capture your live session parameters and test the route immediately.\n")
    try:
        import json
        from pathlib import Path
        from playwright.sync_api import sync_playwright

        session_file = Path.home() / ".notifyseat" / "tcdd_session.json"
        db = Database()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="tr-TR"
            )
            page = context.new_page()

            captured_tokens = []
            captured_headers = {}

            def on_req(req):
                url = req.url
                auth = req.headers.get("authorization", "")
                
                # If Bearer token is found on ANY request
                if auth and "Bearer" in auth:
                    token = auth.replace("Bearer", "").strip()
                    if len(token) > 50 and token not in captured_tokens:
                        captured_tokens.append(token)
                        captured_headers.update(dict(req.headers))
                        cfg = config_mgr.get()
                        cfg.tcdd_token = token
                        config_mgr.save(cfg)
                        print(f"🔑 Live Token captured! ({token[:20]}...)")

                if req.method == "POST" and "tcddtasimacilik.gov.tr" in url:
                    captured_headers.update(dict(req.headers))
                    print(f"📡 [POST] {url}")

            page.on("request", on_req)

            try:
                page.goto("https://ebilet.tcddtasimacilik.gov.tr", wait_until="commit", timeout=60000)
            except Exception as e:
                logger.debug(f"Navigation warning: {e}")

            # Keep window open until user closes it or searches
            for _ in range(300):
                try:
                    if page.is_closed():
                        break
                    # If on search results page or token was captured
                    if ("sefer-listesi" in page.url or "bilet" in page.url) and captured_tokens:
                        time.sleep(2)
                        break
                except Exception:
                    break
                time.sleep(1)

            # Save full session cookies before closing
            try:
                cookies_list = context.cookies()
                cookies_dict = {c["name"]: c["value"] for c in cookies_list}
                session_data = {
                    "timestamp": time.time(),
                    "token": captured_tokens[0] if captured_tokens else config_mgr.get().tcdd_token,
                    "headers": captured_headers,
                    "cookies": cookies_dict
                }
                session_file.parent.mkdir(parents=True, exist_ok=True)
                with open(session_file, "w", encoding="utf-8") as f:
                    json.dump(session_data, f, indent=2)
            except Exception:
                pass

            browser.close()

            print("\n✔ TCDD live session successfully synced!")
            print("⚡ Triggering immediate live route check with your session...\n")
            tasks = db.list_tasks()
            active_tcdd_tasks = [t for t in tasks if t.transport_type == "tcdd" and t.status == TaskStatus.ACTIVE]
            if active_tcdd_tasks:
                for t in active_tcdd_tasks:
                    cmd_check_now(db, config_mgr, t.id)
            else:
                print("No active TCDD tasks found. Create one with: python3 main.py track")

    except Exception as e:
        print(f"Browser connection error: {e}")
    except Exception as e:
        print(f"Browser connection error: {e}")


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
    track_p.add_argument("--time", help="Time filter (e.g. morning, 16:35, 08:00-14:00)")
    track_p.add_argument("--interval", type=int, default=30, help="Check frequency in seconds")
    track_p.add_argument("--channels", default="desktop", help="Comma-separated channels: desktop,telegram,discord,email,sms,webhook")

    # check
    chk_p = subparsers.add_parser("check", help="Trigger an immediate live check for a task (or all active tasks)")
    chk_p.add_argument("task_id", nargs="?", default=None, help="Task ID to check (optional, checks all active if omitted)")

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

    # set-token
    tok_p = subparsers.add_parser("set-token", help="Set TCDD Web/Mobile session Bearer token")
    tok_p.add_argument("token", help="Bearer token copied from TCDD web app / devtools")

    # connect-tcdd
    subparsers.add_parser("connect-tcdd", help="Open browser to capture active TCDD session automatically")
    subparsers.add_parser("connect", help="Alias for connect-tcdd")

    args = parser.parse_args()

    db = Database()
    config_mgr = ConfigManager()

    if not args.command or args.command in ("help", "-h", "--help"):
        print_banner()
        cmd_list(db)
        print("\nCommands available:")
        print("  notifyseat track         ➔ Add a new route to monitor")
        print("  notifyseat run           ➔ Start the background monitoring engine")
        print("  notifyseat check <id>    ➔ Trigger immediate check for a task")
        print("  notifyseat connect-tcdd  ➔ Open browser and connect TCDD session automatically")
        print("  notifyseat set-token <tok> ➔ Set active TCDD session bearer token")
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
    elif args.command == "check":
        cmd_check_now(db, config_mgr, args.task_id)
    elif args.command in ("run", "start"):
        cmd_run(db, config_mgr, args)
    elif args.command in ("connect-tcdd", "connect"):
        cmd_connect_tcdd(config_mgr)
    elif args.command == "set-token":
        cfg = config_mgr.get()
        cfg.tcdd_token = args.token.strip().replace("Bearer ", "")
        config_mgr.save(cfg)
        print(f"✔ TCDD Bearer token saved successfully!")
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
