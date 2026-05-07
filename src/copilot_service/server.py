"""REST server for copilot-service."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from copilot_service.config import ServiceConfig
from copilot_service.runner import run_bridge_request


def create_handler(config: ServiceConfig):
    class RequestHandler(BaseHTTPRequestHandler):
        def _json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._json(HTTPStatus.OK, {"ok": True})
                return
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0:
                    raise ValueError("negative content length")
            except (TypeError, ValueError):
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid Content-Length"})
                return
            body = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid json"})
                return

            if self.path == "/v1/ask":
                response = run_bridge_request(payload, config=config)
                self._json(HTTPStatus.OK, response)
                return

            if self.path == "/v1/tasks/route-topic":
                if isinstance(payload, dict) and "task" in payload:
                    if payload.get("task") != "route-topic":
                        self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "task must be route-topic"})
                        return
                    request = dict(payload)
                    request["task"] = "route-topic"
                else:
                    request = {"task": "route-topic", "input": payload, "options": {}}
                response = run_bridge_request(request, config=config)
                self._json(HTTPStatus.OK, response)
                return

            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

        def log_message(self, format: str, *args: object) -> None:
            return

    return RequestHandler


def run_server(config: ServiceConfig | None = None) -> None:
    cfg = config or ServiceConfig.from_env()
    server = ThreadingHTTPServer((cfg.host, cfg.port), create_handler(cfg))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
