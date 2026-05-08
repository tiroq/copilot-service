"""Provider contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ProviderResult:
    ok: bool
    raw_text: str | None
    stderr: str | None = None
    error: str | None = None
    returncode: int | None = None
    provider_debug: dict | None = None


class Provider:
    name: str = "base"

    def ask(self, prompt: str, model: str, options: dict[str, Any]) -> ProviderResult:  # pragma: no cover - interface
        raise NotImplementedError
