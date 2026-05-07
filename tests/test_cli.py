import io
import json
import os
import pathlib
import py_compile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from copilot_service.cli import main


class CliTests(unittest.TestCase):
    def test_stdin_request(self):
        payload = json.dumps({"task": "freeform", "input": {"prompt": "Explain this"}, "options": {}})
        out = io.StringIO()
        env = {
            "COPILOT_SERVICE_PROVIDER": "fake",
            "COPILOT_SERVICE_FAKE_RESPONSE": "provider response",
        }
        with patch.dict(os.environ, env, clear=False), patch("sys.stdin", io.StringIO(payload)), redirect_stdout(out):
            code = main(["ask", "--stdin"])
        self.assertEqual(code, 0)
        response = json.loads(out.getvalue())
        self.assertTrue(response["ok"])
        self.assertEqual(response["task"], "freeform")
        self.assertEqual(response["content"]["text"], "provider response")

    def test_py_compile_all_source(self):
        root = pathlib.Path(__file__).resolve().parents[1] / "src"
        for py_file in root.rglob("*.py"):
            py_compile.compile(str(py_file), doraise=True)


if __name__ == "__main__":
    unittest.main()
