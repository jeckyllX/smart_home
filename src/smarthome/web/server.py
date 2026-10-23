"""
Embedded HTTP server and REST API for Smart Home dashboard.
Uses standard library http.server.ThreadingHTTPServer for minimal footprint.
"""

from __future__ import annotations

import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from smarthome.web.ui import DASHBOARD_HTML

if TYPE_CHECKING:
    from smarthome.app import SmartHomeApplication

logger = logging.getLogger("SmartHomeWebServer")


class SmartHomeRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request handler exposing dashboard UI and REST endpoints."""

    server: SmartHomeHTTPServer

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(
            "%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args
        )

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html_str: str, status: int = HTTPStatus.OK) -> None:
        payload = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send_html(DASHBOARD_HTML)
        elif path == "/api/state":
            state = self.server.app.get_dashboard_state()
            self._send_json(state)
        elif path == "/api/config":
            cfg_dict = self.server.app.config.to_dict()
            # Redact sensitive keys
            for dev in cfg_dict.get("devices", []):
                if "local_key" in dev:
                    dev["local_key"] = "********"
            self._send_json(cfg_dict)
        else:
            self._send_json({"error": "Not Found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/evaluate":
            logs = self.server.app.evaluate_cycle()
            self._send_json({"success": True, "logs": logs})
            return

        # Pattern: /api/devices/<device_id>/command
        parts = [p for p in path.split("/") if p]
        if (
            len(parts) == 4
            and parts[0] == "api"
            and parts[1] == "devices"
            and parts[3] == "command"
        ):
            device_id = parts[2]
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
                body = json.loads(raw_body)
            except Exception as e:
                self._send_json({"error": f"Invalid JSON body: {e}"}, status=HTTPStatus.BAD_REQUEST)
                return

            action = body.pop("action", None)
            if not action:
                self._send_json(
                    {"error": "Missing 'action' in request body"}, status=HTTPStatus.BAD_REQUEST
                )
                return

            ok, msg = self.server.app.execute_device_command(device_id, str(action), **body)
            status_code = HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST
            self._send_json({"success": ok, "message": msg}, status=status_code)
            return

        self._send_json({"error": "Not Found"}, status=HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/config":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
                data = json.loads(raw_body)
            except Exception as e:
                self._send_json(
                    {"error": f"Invalid JSON payload: {e}"}, status=HTTPStatus.BAD_REQUEST
                )
                return

            try:
                self.server.app.update_config(data)
                self._send_json({"success": True, "message": "Configuration updated and applied."})
            except Exception as e:
                logger.error("Failed to update config: %s", e, exc_info=True)
                self._send_json({"error": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"error": "Not Found"}, status=HTTPStatus.NOT_FOUND)


class SmartHomeHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server carrying reference to the SmartHomeApplication."""

    def __init__(self, server_address: tuple[str, int], app: SmartHomeApplication):
        self.app = app
        super().__init__(server_address, SmartHomeRequestHandler)


class SmartHomeWebServer:
    """Manager for the embedded background Web server."""

    def __init__(self, app: SmartHomeApplication, host: str = "0.0.0.0", port: int = 8765):
        self.app = app
        self.host = host
        self.port = port
        self._server: SmartHomeHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start_background(self) -> None:
        """Start server in a daemon thread."""
        try:
            self._server = SmartHomeHTTPServer((self.host, self.port), self.app)
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="SmartHomeWebThread",
                daemon=True,
            )
            self._thread.start()
            logger.info("Smart Home Web UI listening at http://%s:%d", self.host, self.port)
        except Exception as e:
            logger.error("Failed to start Web server on http://%s:%d: %s", self.host, self.port, e)

    def stop(self) -> None:
        """Stop server gracefully."""
        if self._server:
            logger.info("Stopping Smart Home Web UI...")
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            self._thread = None
