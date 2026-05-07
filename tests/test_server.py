import json
import threading
import unittest
import urllib.error
import urllib.request
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from copilot_service.config import ServiceConfig
from copilot_service.server import create_handler


class ServerTests(unittest.TestCase):
    def test_health(self):
        cfg = ServiceConfig(provider="fake", fake_response="ok")
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(cfg))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload, {"ok": True})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_invalid_content_length_returns_400(self):
        cfg = ServiceConfig(provider="fake", fake_response="ok")
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(cfg))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            conn = HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request(
                "POST",
                "/v1/ask",
                body=b"{}",
                headers={"Content-Type": "application/json", "Content-Length": "abc"},
            )
            response = conn.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            conn.close()
            self.assertEqual(response.status, 400)
            self.assertEqual(payload, {"ok": False, "error": "invalid Content-Length"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_route_topic_endpoint_rejects_mismatched_task(self):
        cfg = ServiceConfig(provider="fake", fake_response="ok")
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(cfg))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/tasks/route-topic",
                data=b'{"task":"freeform","input":{"prompt":"x"},"options":{}}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(ctx.exception.code, 400)
            payload = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertEqual(payload, {"ok": False, "error": "task must be route-topic"})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
