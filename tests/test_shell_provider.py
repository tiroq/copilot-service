import shlex
import sys
import unittest
from unittest.mock import MagicMock, patch

from copilot_service.providers.shell import ShellProvider, _COPILOT_ARGV_FLAGS


class ShellProviderStdinTests(unittest.TestCase):
    """stdin mode: existing behavior using shell=True and stdin."""

    def test_stdin_mode_echoes_prompt(self):
        code = "import sys; print(sys.stdin.read().strip())"
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"
        provider = ShellProvider(command, timeout_seconds=5)
        result = provider.ask("hello", model="gpt-5-mini", options={})
        self.assertTrue(result.ok)
        self.assertEqual(result.raw_text.strip(), "hello")

    def test_stdin_mode_is_default_when_mode_unset(self):
        provider = ShellProvider("echo hi", timeout_seconds=5, mode="")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hi\n", stderr="")
            provider.ask("prompt", model="gpt-5-mini", options={})
            call_kwargs = mock_run.call_args
        # shell=True for stdin mode
        self.assertTrue(call_kwargs.kwargs.get("shell", False))

    def test_stdin_mode_explicit(self):
        provider = ShellProvider("echo hi", timeout_seconds=5, mode="stdin")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hi\n", stderr="")
            provider.ask("prompt", model="gpt-5-mini", options={})
            call_kwargs = mock_run.call_args
        self.assertTrue(call_kwargs.kwargs.get("shell", False))

    def test_stdin_mode_preserves_existing_subprocess_behavior(self):
        """stdin mode passes the prompt via stdin (input=)."""
        provider = ShellProvider("cat", timeout_seconds=5, mode="stdin")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="my-prompt", stderr="")
            provider.ask("my-prompt", model="gpt-5-mini", options={})
            call_kwargs = mock_run.call_args
        self.assertEqual(call_kwargs.kwargs.get("input"), "my-prompt")

    def test_stdin_provider_debug_populated(self):
        code = "import sys; print(sys.stdin.read().strip())"
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"
        provider = ShellProvider(command, timeout_seconds=5, mode="stdin")
        result = provider.ask("hello", model="gpt-5-mini", options={})
        self.assertIsNotNone(result.provider_debug)
        self.assertEqual(result.provider_debug["shell_mode"], "stdin")


class ShellProviderArgvTests(unittest.TestCase):
    """argv mode: shell=False, prompt via -p, model via --model."""

    def _run_argv(self, prompt="test-prompt", model="gpt-5-mini"):
        provider = ShellProvider("/usr/bin/copilot", timeout_seconds=5, mode="argv")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='{"ok":true}', stderr="")
            provider.ask(prompt, model=model, options={})
            return mock_run.call_args

    def test_argv_mode_uses_shell_false(self):
        call = self._run_argv()
        self.assertFalse(call.kwargs.get("shell", True))

    def test_argv_mode_passes_prompt_via_p_flag(self):
        call = self._run_argv(prompt="hello world")
        argv = call.args[0]
        self.assertIn("-p", argv)
        idx = argv.index("-p")
        self.assertEqual(argv[idx + 1], "hello world")

    def test_argv_mode_passes_model_flag(self):
        call = self._run_argv(model="gpt-5-mini")
        argv = call.args[0]
        self.assertIn("--model", argv)
        idx = argv.index("--model")
        self.assertEqual(argv[idx + 1], "gpt-5-mini")

    def test_argv_mode_includes_silent(self):
        argv = self._run_argv().args[0]
        self.assertIn("--silent", argv)

    def test_argv_mode_includes_no_color(self):
        argv = self._run_argv().args[0]
        self.assertIn("--no-color", argv)

    def test_argv_mode_includes_no_auto_update(self):
        argv = self._run_argv().args[0]
        self.assertIn("--no-auto-update", argv)

    def test_argv_mode_includes_stream_off(self):
        argv = self._run_argv().args[0]
        self.assertIn("--stream", argv)
        idx = argv.index("--stream")
        self.assertEqual(argv[idx + 1], "off")

    def test_argv_mode_includes_no_custom_instructions(self):
        argv = self._run_argv().args[0]
        self.assertIn("--no-custom-instructions", argv)

    def test_argv_mode_includes_no_ask_user(self):
        argv = self._run_argv().args[0]
        self.assertIn("--no-ask-user", argv)

    def test_argv_mode_includes_available_tools_empty(self):
        argv = self._run_argv().args[0]
        self.assertIn("--available-tools=", argv)

    def test_argv_mode_does_not_include_ask(self):
        argv = self._run_argv().args[0]
        self.assertNotIn("ask", argv)

    def test_argv_mode_does_not_include_stdin_flag(self):
        argv = self._run_argv().args[0]
        self.assertNotIn("--stdin", argv)

    def test_argv_mode_command_is_first_element(self):
        argv = self._run_argv().args[0]
        self.assertEqual(argv[0], "/usr/bin/copilot")

    def test_argv_mode_provider_debug(self):
        provider = ShellProvider("/usr/bin/copilot", timeout_seconds=5, mode="argv")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='{"ok":true}', stderr="")
            result = provider.ask("hello", model="gpt-5-mini", options={})
        self.assertIsNotNone(result.provider_debug)
        dbg = result.provider_debug
        self.assertEqual(dbg["shell_mode"], "argv")
        self.assertEqual(dbg["command"], "/usr/bin/copilot")
        self.assertEqual(dbg["return_code"], 0)
        self.assertIn("stdout_len", dbg)
        self.assertIn("stderr_len", dbg)

    def test_argv_mode_no_input_kwarg(self):
        """argv mode must not pass input= (no stdin piping)."""
        call = self._run_argv()
        self.assertNotIn("input", call.kwargs)

    def test_argv_real_execution(self):
        """Integration: argv mode passes prompt via -p to a real subprocess."""
        import os
        import stat
        import tempfile

        # A shell script that walks argv and prints the value after -p
        script = (
            "#!/bin/sh\n"
            "prev=\n"
            "for a in \"$@\"; do\n"
            "  [ \"$prev\" = \"-p\" ] && printf '%s' \"$a\" && exit 0\n"
            "  prev=\"$a\"\n"
            "done\n"
            "exit 1\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write(script)
            script_path = f.name
        os.chmod(script_path, stat.S_IRWXU)
        try:
            provider = ShellProvider(script_path, timeout_seconds=5, mode="argv")
            with patch("copilot_service.providers.shell._COPILOT_ARGV_FLAGS", []):
                result = provider.ask("real-prompt", model="any", options={})
            self.assertTrue(result.ok)
            self.assertIn("real-prompt", result.raw_text)
        finally:
            os.unlink(script_path)


class ShellProviderInvalidOutputTests(unittest.TestCase):
    def test_invalid_provider_output_includes_debug_in_result(self):
        provider = ShellProvider("/usr/bin/copilot", timeout_seconds=5, mode="argv")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="some stderr")
            result = provider.ask("hello", model="gpt-5-mini", options={})
        # provider_debug must carry diagnostics even when output is invalid
        self.assertIsNotNone(result.provider_debug)
        self.assertEqual(result.provider_debug["return_code"], 0)


if __name__ == "__main__":
    unittest.main()
