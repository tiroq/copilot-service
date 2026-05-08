"""Tests for terminal.py formatting helpers and CLI welcome/version behavior."""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from copilot_service.terminal import render_welcome, supports_color
from copilot_service.cli import main


class SupportsColorTests(unittest.TestCase):
    def test_no_color_env_disables(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            self.assertFalse(supports_color(io.StringIO()))

    def test_non_tty_disables(self):
        # StringIO has no isatty that returns True
        self.assertFalse(supports_color(io.StringIO()))

    def test_no_isatty_attr_disables(self):
        class FakeStream:
            pass
        self.assertFalse(supports_color(FakeStream()))


class RenderWelcomeTests(unittest.TestCase):
    def _plain(self, version: str = "1.2.3") -> str:
        return render_welcome(version, color_enabled=False)

    def test_contains_copilot_caas(self):
        self.assertIn("Copilot CaaS", self._plain())

    def test_contains_version(self):
        self.assertIn("1.2.3", self._plain("1.2.3"))

    def test_contains_commands(self):
        text = self._plain()
        self.assertIn("ask", text)
        self.assertIn("serve", text)

    def test_contains_docs_url(self):
        self.assertIn("tiroq/copilot-service", self._plain())

    def test_no_ansi_when_color_disabled(self):
        text = self._plain()
        self.assertNotIn("\033[", text)

    def test_ansi_present_when_color_enabled(self):
        text = render_welcome("0.1.0", color_enabled=True)
        self.assertIn("\033[", text)


class CliNoArgsTests(unittest.TestCase):
    def test_no_args_exits_zero(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([])
        self.assertEqual(code, 0)

    def test_no_args_output_contains_copilot_caas(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([])
        self.assertIn("Copilot CaaS", out.getvalue())

    def test_no_args_output_contains_ask_and_serve(self):
        out = io.StringIO()
        with redirect_stdout(out):
            main([])
        text = out.getvalue()
        self.assertIn("ask", text)
        self.assertIn("serve", text)

    def test_no_color_env_produces_no_ansi(self):
        out = io.StringIO()
        with patch.dict(os.environ, {"NO_COLOR": "1"}), redirect_stdout(out):
            main([])
        self.assertNotIn("\033[", out.getvalue())


class CliVersionTests(unittest.TestCase):
    def test_version_flag_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_version_flag_output(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit), patch("sys.stdout", out):
            main(["--version"])
        self.assertIn("copilot-caas", out.getvalue())


if __name__ == "__main__":
    unittest.main()
