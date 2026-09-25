"""Stdlib HTTP server for the LAN research dashboard."""

from __future__ import annotations

import asyncio
import logging
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from src.config import Settings, get_settings
from src.dashboard.html import WINDOWS, render_dashboard
from src.storage import Database

logger = logging.getLogger(__name__)


class _DashboardState:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings)
        self.loop = asyncio.new_event_loop()
        self._lock = threading.Lock()
        self.loop.run_until_complete(self.db.init())

    def load(self, window: str) -> dict:
        if window not in WINDOWS:
            window = "7d"
        with self._lock:
            return self.loop.run_until_complete(self.db.load_dashboard_payload(window=window))

    def close(self) -> None:
        with self._lock:
            try:
                self.loop.run_until_complete(self.db.close())
            finally:
                self.loop.close()


def _make_handler(state: _DashboardState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            logger.info("%s - %s", self.address_string(), fmt % args)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in {"/", "/index.html", "/dashboard"}:
                self.send_error(404, "Not found")
                return

            qs = parse_qs(parsed.query)
            window = (qs.get("window") or ["7d"])[0]
            try:
                payload = state.load(window)
                body = render_dashboard(payload).encode("utf-8")
            except Exception:  # noqa: BLE001
                logger.exception("Dashboard render failed")
                self.send_error(500, "Dashboard query failed")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve_dashboard(
    settings: Optional[Settings] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> None:
    settings = settings or get_settings()
    host = host if host is not None else settings.dashboard_host
    port = port if port is not None else settings.dashboard_port

    state = _DashboardState(settings)
    handler = _make_handler(state)
    server = ThreadingHTTPServer((host, port), handler)

    def _shutdown(*_args) -> None:
        logger.info("Shutting down dashboard server")
        server.shutdown()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except ValueError:
            # Not main thread
            pass

    logger.info(
        "Dashboard listening on http://%s:%s (LAN check-in; read-only; no auth)",
        host,
        port,
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
        state.close()
