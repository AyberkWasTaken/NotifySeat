"""Local Web GUI Server & REST API for NotifySeat."""
import http.server
import socketserver
import json
import urllib.parse
import os
import mimetypes
import webbrowser
import queue
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from notifyseat.core.models import TrackingTask, TransportType, TaskStatus
from notifyseat.core.database import Database
from notifyseat.core.config import ConfigManager
from notifyseat.core.logger import logger
from notifyseat.notifiers.manager import NotificationManager
from notifyseat.engine.scheduler import EngineScheduler
from notifyseat.providers.registry import registry


PACKAGE_DIR = Path(__file__).parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"


class SSEManager:
    """Manages Server-Sent Events client queues for real-time live updates."""
    def __init__(self):
        self.clients: List[queue.Queue] = []

    def add_client(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        self.clients.append(q)
        return q

    def remove_client(self, q: queue.Queue):
        if q in self.clients:
            self.clients.remove(q)

    def broadcast(self, event_type: str, data: Dict[str, Any]):
        msg = f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"
        for q in list(self.clients):
            try:
                q.put_nowait(msg)
            except Exception:
                pass


class NotifySeatHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Handles HTTP requests for NotifySeat Local Web Dashboard."""

    # Injected by server runner
    db: Database = None
    config_mgr: ConfigManager = None
    scheduler: EngineScheduler = None
    notifier_mgr: NotificationManager = None
    sse_mgr: SSEManager = None

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging in terminal
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Index Page
        if path == "/" or path == "/index.html":
            self._serve_file(TEMPLATES_DIR / "index.html", "text/html; charset=utf-8")
            return

        # 2. Static Assets
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            file_path = STATIC_DIR / rel_path
            mime_type, _ = mimetypes.guess_type(str(file_path))
            self._serve_file(file_path, mime_type or "application/octet-stream")
            return

        # 3. SSE Live Events Stream
        if path == "/api/events":
            self._handle_sse()
            return

        # 4. REST API Endpoints
        if path == "/api/stats":
            stats = self.db.get_stats()
            stats["engine_running"] = self.scheduler.is_running()
            self._send_json(stats)
            return

        if path == "/api/tasks":
            tasks = self.db.list_tasks()
            self._send_json([t.to_dict() for t in tasks])
            return

        if path == "/api/config":
            self._send_json(self.config_mgr.get().to_dict())
            return

        if path == "/api/popular-routes":
            transport_str = query.get("transport", ["tcdd"])[0]
            transport = TransportType.from_str(transport_str)
            provider = registry.get(transport)
            self._send_json(provider.get_popular_routes())
            return

        if path == "/api/stations":
            transport_str = query.get("transport", ["tcdd"])[0]
            q_str = query.get("query", [""])[0]
            transport = TransportType.from_str(transport_str)
            provider = registry.get(transport)
            self._send_json(provider.search_stations(q_str))
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/tasks":
            task = TrackingTask(
                transport_type=TransportType.from_str(body.get("transport_type", "tcdd")),
                origin=body.get("origin", ""),
                origin_id=body.get("origin_id"),
                destination=body.get("destination", ""),
                destination_id=body.get("destination_id"),
                date=body.get("date", datetime.now().strftime("%Y-%m-%d")),
                time_filter=body.get("time_filter"),
                seat_class=body.get("seat_class", "ANY"),
                check_interval_seconds=int(body.get("check_interval_seconds", 30)),
                notification_channels=body.get("notification_channels", ["desktop"]),
                status=TaskStatus.ACTIVE
            )
            saved = self.db.create_task(task)
            self._send_json(saved.to_dict(), status_code=201)
            return

        if path.startswith("/api/tasks/") and path.endswith("/pause"):
            task_id = path.split("/")[3]
            self.db.update_task_status(task_id, TaskStatus.PAUSED)
            self._send_json({"success": True, "status": "paused"})
            return

        if path.startswith("/api/tasks/") and path.endswith("/resume"):
            task_id = path.split("/")[3]
            self.db.update_task_status(task_id, TaskStatus.ACTIVE)
            self._send_json({"success": True, "status": "active"})
            return

        if path.startswith("/api/tasks/") and path.endswith("/check"):
            task_id = path.split("/")[3]
            success = self.scheduler.trigger_task_now(task_id)
            self._send_json({"success": success})
            return

        if path == "/api/config":
            current_cfg = self.config_mgr.get().to_dict()
            if "telegram" in body:
                current_cfg["telegram"].update(body["telegram"])
            if "discord" in body:
                current_cfg["discord"].update(body["discord"])
            if "desktop" in body:
                current_cfg["desktop"].update(body["desktop"])
            if "email" in body:
                current_cfg["email"].update(body["email"])
            if "tcdd_token" in body:
                current_cfg["tcdd_token"] = body["tcdd_token"].strip().replace("Bearer ", "")
            
            from notifyseat.core.config import AppConfig
            new_cfg = AppConfig.from_dict(current_cfg)
            self.config_mgr.save(new_cfg)
            self.notifier_mgr.reload(new_cfg)
            self._send_json({"success": True})
            return

        if path == "/api/tcdd/connect":
            # 1-Click Connect TCDD
            token = body.get("token", "").strip().replace("Bearer ", "")
            if not token:
                # Try discovery from known production tokens or Playwright
                from notifyseat.providers.tcdd import TCDDProvider
                provider = TCDDProvider()
                token = provider.JWT_TOKENS[0] if provider.JWT_TOKENS else ""

            cfg = self.config_mgr.get()
            if token:
                cfg.tcdd_token = token
                self.config_mgr.save(cfg)
                self._send_json({"success": True, "connected": True, "token": token[:30] + "..."})
            else:
                self._send_json({"success": False, "connected": False, "error": "Could not auto-connect TCDD"})
            return

        if path == "/api/tcdd/set-token":
            token = body.get("token", "").strip().replace("Bearer ", "")
            cfg = self.config_mgr.get()
            cfg.tcdd_token = token
            self.config_mgr.save(cfg)
            self._send_json({"success": True, "connected": bool(token)})
            return

        if path == "/api/test-notify":
            channel = body.get("channel", "desktop")
            success = self.notifier_mgr.test_channel(channel)
            self._send_json({"success": success})
            return

        if path == "/api/engine/start":
            self.scheduler.start()
            self._send_json({"success": True, "running": True})
            return

        if path == "/api/engine/stop":
            self.scheduler.stop()
            self._send_json({"success": True, "running": False})
            return

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/tasks/"):
            task_id = path.split("/")[3]
            success = self.db.delete_task(task_id)
            self._send_json({"success": success})
            return
        self.send_error(404, "Not Found")

    def _serve_file(self, file_path: Path, content_type: str):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File Not Found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: Any, status_code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        client_queue = self.sse_mgr.add_client()
        try:
            while True:
                try:
                    msg = client_queue.get(timeout=20)
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Ping keepalive
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.sse_mgr.remove_client(client_queue)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_web_server(host: str = "127.0.0.1", port: int = 8080, auto_open: bool = True):
    """Starts the local Web GUI server and scheduler."""
    db = Database()
    config_mgr = ConfigManager()
    cfg = config_mgr.get()
    notifier_mgr = NotificationManager(cfg, db)
    scheduler = EngineScheduler(db, cfg, notifier_mgr)
    sse_mgr = SSEManager()

    # Link scheduler events to SSE broadcast
    scheduler.subscribe_events(sse_mgr.broadcast)
    scheduler.start()

    # Inject dependencies into request handler
    NotifySeatHTTPHandler.db = db
    NotifySeatHTTPHandler.config_mgr = config_mgr
    NotifySeatHTTPHandler.scheduler = scheduler
    NotifySeatHTTPHandler.notifier_mgr = notifier_mgr
    NotifySeatHTTPHandler.sse_mgr = sse_mgr

    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, NotifySeatHTTPHandler)

    url = f"http://{host}:{port}"
    print(f"\n========================================================")
    print(f"  🚀 \033[1;32mNotifySeat Web GUI is running at: {url}\033[0m")
    print(f"  • Local-first: 100% running on your machine")
    print(f"  • Live seat & cancellation monitoring active")
    print(f"  • Press Ctrl+C to stop")
    print(f"========================================================\n")

    if auto_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NotifySeat Web GUI...")
        scheduler.stop()
        httpd.server_close()
        print("✔ NotifySeat Web GUI stopped.")
