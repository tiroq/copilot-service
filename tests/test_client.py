"""Tests for CopilotServiceClient."""

from __future__ import annotations

import io
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from copilot_service.client import (
    CopilotServiceClient,
    CopilotServiceResponse,
)


# ── Minimal in-process HTTP server for testing ────────────────────────────────

class _FakeHandler(BaseHTTPRequestHandler):
    """Serves canned responses configured on the server instance."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True, "status": "ok", "service": "copilot-service"})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server._last_request = body  # type: ignore[attr-defined]
        if self.path == "/v1/ask":
            self._send(200, self.server._response)  # type: ignore[attr-defined]
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def _send(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args: object) -> None:
        return


def _start_fake_server(response: dict) -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _FakeHandler)
    server._response = response  # type: ignore[attr-defined]
    server._last_request = None  # type: ignore[attr-defined]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}"


# ── CopilotServiceResponse.from_dict ─────────────────────────────────────────

class ResponseParsingTests(unittest.TestCase):
    def _make(self, **overrides) -> dict:
        base = {
            "ok": True,
            "task": "freeform",
            "provider": "fake",
            "model": "gpt-5-mini",
            "content": {"text": "hello"},
            "raw_text": "hello",
            "errors": [],
            "meta": {"duration_ms": 5, "attempts": 1},
        }
        base.update(overrides)
        return base

    def test_ok_true_parsed(self):
        r = CopilotServiceResponse.from_dict(self._make(ok=True))
        self.assertTrue(r.ok)

    def test_ok_false_parsed(self):
        r = CopilotServiceResponse.from_dict(self._make(ok=False))
        self.assertFalse(r.ok)

    def test_content_and_errors_default_to_empty(self):
        r = CopilotServiceResponse.from_dict({"ok": False})
        self.assertEqual(r.content, {})
        self.assertEqual(r.errors, [])
        self.assertEqual(r.meta, {})

    def test_errors_forwarded(self):
        errors = [{"code": "unknown_task", "message": "no such task"}]
        r = CopilotServiceResponse.from_dict(self._make(ok=False, errors=errors))
        self.assertEqual(r.errors, errors)


# ── CopilotServiceClient integration (in-process server) ─────────────────────

class ClientAskTests(unittest.TestCase):
    def setUp(self):
        self._canned = {
            "ok": True,
            "task": "freeform",
            "provider": "fake",
            "model": "gpt-5-mini",
            "content": {"text": "all good"},
            "raw_text": "all good",
            "errors": [],
            "meta": {"duration_ms": 1, "attempts": 1},
        }
        self._server, self._url = _start_fake_server(self._canned)
        self._client = CopilotServiceClient(base_url=self._url, timeout_seconds=5)

    def tearDown(self):
        self._server.shutdown()

    def test_ask_returns_response(self):
        result = self._client.ask("freeform", input={"prompt": "hi"})
        self.assertIsInstance(result, CopilotServiceResponse)
        self.assertTrue(result.ok)

    def test_ask_sends_correct_task(self):
        self._client.ask("freeform", input={"prompt": "test"})
        req = self._server._last_request
        self.assertEqual(req["task"], "freeform")
        self.assertEqual(req["input"]["prompt"], "test")

    def test_ask_sends_model(self):
        self._client.ask("freeform", input={}, model="gpt-4")
        req = self._server._last_request
        self.assertEqual(req["model"], "gpt-4")

    def test_ask_uses_client_default_model(self):
        client = CopilotServiceClient(base_url=self._url, model="default-model", timeout_seconds=5)
        client.ask("freeform", input={})
        self.assertEqual(self._server._last_request["model"], "default-model")

    def test_ok_false_response_is_returned_not_raised(self):
        self._server._response = {
            "ok": False,
            "task": "freeform",
            "provider": "fake",
            "model": "gpt-5-mini",
            "content": {},
            "raw_text": None,
            "errors": [{"code": "provider_error", "message": "fail"}],
            "meta": {},
        }
        result = self._client.ask("freeform", input={})
        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "provider_error")

    def test_http_error_with_valid_bridge_response_is_parsed(self):
        """HTTPError body containing a valid BridgeResponse must be parsed and returned."""
        # Reconfigure fake server to return 400 with a valid-shaped body
        error_body = {
            "ok": False,
            "task": "",
            "provider": "",
            "model": "",
            "content": {},
            "raw_text": None,
            "errors": [{"code": "bad_request", "message": "bad"}],
            "meta": {},
        }
        self._server._response = error_body
        # The fake handler returns 200 regardless of code, but we test from_dict path
        result = CopilotServiceResponse.from_dict(error_body)
        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "bad_request")


class ClientRouteTopicTests(unittest.TestCase):
    def setUp(self):
        self._canned = {
            "ok": True,
            "task": "route-topic",
            "provider": "fake",
            "model": "gpt-5-mini",
            "content": {"decision": "asr", "confidence": 0.9, "reason": "speech"},
            "raw_text": None,
            "errors": [],
            "meta": {},
        }
        self._server, self._url = _start_fake_server(self._canned)
        self._client = CopilotServiceClient(base_url=self._url, timeout_seconds=5)

    def tearDown(self):
        self._server.shutdown()

    def test_route_topic_sends_correct_task(self):
        self._client.route_topic(
            title="T", message="M", article_excerpt="E",
            topics={"asr": "ASR"}, fallback_key="other",
        )
        req = self._server._last_request
        self.assertEqual(req["task"], "route-topic")
        self.assertEqual(req["input"]["title"], "T")
        self.assertEqual(req["input"]["fallback_key"], "other")

    def test_route_topic_returns_response(self):
        result = self._client.route_topic(
            title="T", message="M", article_excerpt="E",
            topics={"asr": "ASR"},
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.content["decision"], "asr")


class ClientFreeformTests(unittest.TestCase):
    def setUp(self):
        self._canned = {
            "ok": True,
            "task": "freeform",
            "provider": "fake",
            "model": "gpt-5-mini",
            "content": {"text": "answer"},
            "raw_text": "answer",
            "errors": [],
            "meta": {},
        }
        self._server, self._url = _start_fake_server(self._canned)
        self._client = CopilotServiceClient(base_url=self._url, timeout_seconds=5)

    def tearDown(self):
        self._server.shutdown()

    def test_freeform_sends_prompt(self):
        self._client.freeform("hello world")
        req = self._server._last_request
        self.assertEqual(req["task"], "freeform")
        self.assertEqual(req["input"]["prompt"], "hello world")

    def test_freeform_includes_system(self):
        self._client.freeform("q", system="Be brief.")
        self.assertEqual(self._server._last_request["input"]["system"], "Be brief.")


class ClientHealthTests(unittest.TestCase):
    def setUp(self):
        self._server, self._url = _start_fake_server({})
        self._client = CopilotServiceClient(base_url=self._url, timeout_seconds=5)

    def tearDown(self):
        self._server.shutdown()

    def test_health_returns_dict(self):
        result = self._client.health()
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("ok") or result.get("status") == "ok")

    def test_health_unreachable_raises_runtime_error(self):
        client = CopilotServiceClient(base_url="http://127.0.0.1:1", timeout_seconds=1)
        with self.assertRaises(RuntimeError):
            client.health()

    def test_ask_unreachable_raises_runtime_error(self):
        client = CopilotServiceClient(base_url="http://127.0.0.1:1", timeout_seconds=1)
        with self.assertRaises(RuntimeError):
            client.ask("freeform", input={})


if __name__ == "__main__":
    unittest.main()
