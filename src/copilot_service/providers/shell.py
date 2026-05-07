"""Shell command provider."""

from __future__ import annotations

import subprocess
from typing import Any

from .base import Provider, ProviderResult


class ShellProvider(Provider):
    name = "shell"

    def __init__(self, command: str, timeout_seconds: int = 90) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds

    def ask(self, prompt: str, model: str, options: dict[str, Any]) -> ProviderResult:
        if not self.command:
            return ProviderResult(ok=False, raw_text=None, error="shell command is not configured")
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
            return ProviderResult(
                ok=result.returncode == 0,
                raw_text=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                error=None if result.returncode == 0 else "provider command failed",
            )
        except subprocess.TimeoutExpired as exc:
            return ProviderResult(
                ok=False,
                raw_text=exc.stdout,
                stderr=exc.stderr,
                error="provider timeout",
            )
        except OSError as exc:
            return ProviderResult(ok=False, raw_text=None, error=f"provider execution error: {exc}")
