"""Request/response contracts for the bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BridgeRequest:
    task: str
    model: str | None = None
    input: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BridgeResponse:
    ok: bool
    task: str
    provider: str
    model: str
    content: dict[str, Any]
    raw_text: str | None
    errors: list[dict[str, str]]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "task": self.task,
            "provider": self.provider,
            "model": self.model,
            "content": self.content,
            "raw_text": self.raw_text,
            "errors": self.errors,
            "meta": self.meta,
        }
