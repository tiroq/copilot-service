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

    def test_invalid_stdin_json_returns_error_code(self):
        out = io.StringIO()
        with patch("sys.stdin", io.StringIO("{")), redirect_stdout(out):
            code = main(["ask", "--stdin"])
        self.assertEqual(code, 2)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["code"], "invalid_request")

    def test_unknown_task_returns_non_zero_exit(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["ask", "--task", "missing-task"])
        self.assertEqual(code, 1)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
