"""Main request runner."""

from __future__ import annotations

import time
from typing import Any

from copilot_service.config import ServiceConfig
from copilot_service.contracts import BridgeRequest, BridgeResponse
from copilot_service.providers import create_provider
from copilot_service.providers.base import Provider
from copilot_service.tasks import TASKS


def run_bridge_request(request_payload: dict[str, Any], config: ServiceConfig | None = None, provider: Provider | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    cfg = config or ServiceConfig.from_env()
    errors: list[dict[str, str]] = []

    req = BridgeRequest(
        task=str(request_payload.get("task", "")),
        model=request_payload.get("model") or cfg.model,
        input=request_payload.get("input") or {},
        options=request_payload.get("options") or {},
    )

    if req.task not in TASKS:
        return _response(
            ok=False,
            task=req.task or "",
            provider=cfg.provider,
            model=req.model,
            content={},
            raw_text=None,
            errors=[{"code": "unknown_task", "message": f"unsupported task: {req.task}"}],
            started=started,
        )

    task_impl = TASKS[req.task]
    prompt = task_impl.build_prompt(req.input)
    active_provider = provider or create_provider(cfg)
    provider_result = active_provider.ask(prompt, req.model, req.options)

    if provider_result.error:
        errors.append({"code": "provider_error", "message": provider_result.error})

    parsed_ok, content, parse_errors = task_impl.parse_output(provider_result.raw_text, req.input, req.options)
    errors.extend(parse_errors)

    ok = parsed_ok and provider_result.ok and (req.task != "route-topic" or bool(content))
    return _response(
        ok=ok,
        task=req.task,
        provider=active_provider.name,
        model=req.model,
        content=content,
        raw_text=provider_result.raw_text,
        errors=errors,
        started=started,
    )


def _response(
    *,
    ok: bool,
    task: str,
    provider: str,
    model: str,
    content: dict[str, Any],
    raw_text: str | None,
    errors: list[dict[str, str]],
    started: float,
) -> dict[str, Any]:
    duration_ms = int((time.perf_counter() - started) * 1000)
    response = BridgeResponse(
        ok=ok,
        task=task,
        provider=provider,
        model=model,
        content=content,
        raw_text=raw_text,
        errors=errors,
        meta={"duration_ms": duration_ms, "attempts": 1},
    )
    return response.to_dict()
