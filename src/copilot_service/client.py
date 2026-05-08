"""Python client library for the copilot-service local REST API.

Uses stdlib only — no external dependencies.

Example::

    from copilot_service.client import CopilotServiceClient

    client = CopilotServiceClient()
    result = client.freeform("Explain this error")
    if result.ok:
        print(result.content["text"])
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_MODEL = "gpt-5-mini"


@dataclass(slots=True)
class CopilotServiceResponse:
    ok: bool
    task: str
    provider: str
    model: str
    content: dict[str, Any]
    raw_text: str | None
    errors: list[dict[str, str]]
    meta: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CopilotServiceResponse":
        return cls(
            ok=bool(data.get("ok", False)),
            task=str(data.get("task", "")),
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            content=data.get("content") or {},
            raw_text=data.get("raw_text"),
            errors=data.get("errors") or [],
            meta=data.get("meta") or {},
        )


@dataclass(slots=True)
class CopilotServiceError(Exception):
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class CopilotServiceClient:
    """Minimal HTTP client for the copilot-service local REST API.

    Args:
        base_url: Base URL of the running copilot-service instance.
        timeout_seconds: Request timeout. Raise ``RuntimeError`` on timeout.
        model: Default model to use when not overridden per-call.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.model = model

    # ── Low-level helpers ────────────────────────────────────────────────────

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"copilot-service unreachable at {self.base_url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"copilot-service request timed out after {self.timeout_seconds}s") from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"copilot-service returned non-JSON response: {raw[:200]!r}") from exc

    # ── Public API ───────────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        """Call GET /health. Returns the raw response dict.

        Raises ``RuntimeError`` if the service is unreachable or returns non-JSON.
        """
        url = f"{self.base_url}/health"
        req = urllib.request.Request(url=url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"copilot-service unreachable at {self.base_url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeError(f"copilot-service /health timed out") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"copilot-service /health returned non-JSON: {raw[:200]!r}") from exc

    def ask(
        self,
        task: str,
        input: dict[str, Any],  # noqa: A002
        *,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> CopilotServiceResponse:
        """Send a generic task request to POST /v1/ask.

        Does not raise for ``ok=False`` responses — the caller must inspect
        ``result.ok`` and ``result.errors``.

        Raises ``RuntimeError`` only for transport failures or non-JSON service response.
        """
        payload: dict[str, Any] = {
            "task": task,
            "model": model or self.model,
            "input": input,
            "options": options or {},
        }
        data = self._post("/v1/ask", payload)
        return CopilotServiceResponse.from_dict(data)

    def route_topic(
        self,
        title: str,
        message: str,
        article_excerpt: str,
        topics: dict[str, Any],
        *,
        fallback_key: str = "fallback",
        model: str | None = None,
    ) -> CopilotServiceResponse:
        """Helper for the ``route-topic`` task."""
        return self.ask(
            task="route-topic",
            input={
                "title": title,
                "message": message,
                "article_excerpt": article_excerpt,
                "topics": topics,
                "fallback_key": fallback_key,
            },
            model=model,
        )

    def freeform(
        self,
        prompt: str,
        *,
        system: str = "You are a concise engineering assistant.",
        model: str | None = None,
    ) -> CopilotServiceResponse:
        """Helper for the ``freeform`` task."""
        return self.ask(
            task="freeform",
            input={"prompt": prompt, "system": system},
            model=model,
        )
