"""Fake provider for tests and local dry-runs."""

from __future__ import annotations

from typing import Any

from .base import Provider, ProviderResult


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, default_output: str = "") -> None:
        self.default_output = default_output

    def ask(self, prompt: str, model: str, options: dict[str, Any]) -> ProviderResult:
        text = options.get("fake_output") or self.default_output or prompt
        return ProviderResult(ok=True, raw_text=str(text), returncode=0)
