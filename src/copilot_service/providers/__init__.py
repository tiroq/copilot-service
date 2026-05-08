"""Provider factory."""

from __future__ import annotations

from copilot_service.config import ServiceConfig

from .base import Provider
from .fake import FakeProvider
from .shell import ShellProvider


def create_provider(config: ServiceConfig) -> Provider:
    if config.provider == "fake":
        return FakeProvider(default_output=config.fake_response)
    return ShellProvider(command=config.shell_command, timeout_seconds=config.timeout_seconds, mode=config.shell_mode)
