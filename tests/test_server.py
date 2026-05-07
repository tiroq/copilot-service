import json
import threading
import unittest
import urllib.request
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


if __name__ == "__main__":
    unittest.main()
