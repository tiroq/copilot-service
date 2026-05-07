"""Configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class ServiceConfig:
    provider: str = "shell"
    shell_command: str = ""
    model: str = "gpt-5-mini"
    timeout_seconds: int = 90
    host: str = "127.0.0.1"
    port: int = 8765
    fake_response: str = ""

    @classmethod
    def from_env(cls) -> "ServiceConfig":
        return cls(
            provider=os.getenv("COPILOT_SERVICE_PROVIDER", "shell").strip() or "shell",
            shell_command=os.getenv("COPILOT_SERVICE_SHELL_COMMAND", "").strip(),
            model=os.getenv("COPILOT_SERVICE_MODEL", "gpt-5-mini").strip() or "gpt-5-mini",
            timeout_seconds=_parse_int(os.getenv("COPILOT_SERVICE_TIMEOUT_SECONDS"), 90),
            host=os.getenv("COPILOT_SERVICE_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_parse_int(os.getenv("COPILOT_SERVICE_PORT"), 8765),
            fake_response=os.getenv("COPILOT_SERVICE_FAKE_RESPONSE", ""),
        )


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
