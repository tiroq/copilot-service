"""Shell command provider."""

from __future__ import annotations

import subprocess
from typing import Any

from .base import Provider, ProviderResult

# Fixed flags appended in argv mode for the GitHub Copilot CLI.
_COPILOT_ARGV_FLAGS: list[str] = [
    "--silent",
    "--no-color",
    "--no-auto-update",
    "--stream",
    "off",
    "--no-custom-instructions",
    "--no-ask-user",
    "--available-tools=",
]


class ShellProvider(Provider):
    name = "shell"

    def __init__(self, command: str, timeout_seconds: int = 90, mode: str = "") -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        # mode: "" | "stdin" | "argv"
        self.mode = mode.strip().lower() if mode else ""

    def ask(self, prompt: str, model: str, options: dict[str, Any]) -> ProviderResult:
        if not self.command:
            return ProviderResult(ok=False, raw_text=None, error="shell command is not configured")
        if self.mode == "argv":
            return self._ask_argv(prompt, model)
        return self._ask_stdin(prompt)

    # ------------------------------------------------------------------
    # argv mode: executable path only, no shell=True, prompt via -p flag
    # ------------------------------------------------------------------

    def _ask_argv(self, prompt: str, model: str) -> ProviderResult:
        argv = [self.command, "-p", prompt, "--model", model, *_COPILOT_ARGV_FLAGS]
        debug: dict[str, Any] = {"shell_mode": "argv", "command": self.command}
        try:
            result = subprocess.run(
                argv,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
            debug["return_code"] = result.returncode
            debug["stdout_len"] = len(result.stdout or "")
            debug["stderr_len"] = len(result.stderr or "")
            return ProviderResult(
                ok=result.returncode == 0,
                raw_text=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                error=None if result.returncode == 0 else "provider command failed",
                provider_debug=debug,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else None)
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else None)
            debug["return_code"] = None
            debug["stdout_len"] = len(stdout or "")
            debug["stderr_len"] = len(stderr or "")
            return ProviderResult(ok=False, raw_text=stdout, stderr=stderr, error="provider timeout", provider_debug=debug)
        except OSError as exc:
            return ProviderResult(ok=False, raw_text=None, error=f"provider execution error: {exc}", provider_debug=debug)

    # ------------------------------------------------------------------
    # stdin mode (default): original shell=True behavior, prompt via stdin
    # ------------------------------------------------------------------

    def _ask_stdin(self, prompt: str) -> ProviderResult:
        debug: dict[str, Any] = {"shell_mode": self.mode or "stdin", "command": self.command}
        try:
            result = subprocess.run(
                self.command,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                shell=True,
                check=False,
            )
            debug["return_code"] = result.returncode
            debug["stdout_len"] = len(result.stdout or "")
            debug["stderr_len"] = len(result.stderr or "")
            return ProviderResult(
                ok=result.returncode == 0,
                raw_text=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                error=None if result.returncode == 0 else "provider command failed",
                provider_debug=debug,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", errors="replace") if exc.stdout else None)
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else None)
            debug["return_code"] = None
            debug["stdout_len"] = len(stdout or "")
            debug["stderr_len"] = len(stderr or "")
            return ProviderResult(ok=False, raw_text=stdout, stderr=stderr, error="provider timeout", provider_debug=debug)
        except OSError as exc:
            return ProviderResult(ok=False, raw_text=None, error=f"provider execution error: {exc}", provider_debug=debug)

