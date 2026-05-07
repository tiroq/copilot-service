"""route-topic task logic."""

from __future__ import annotations

from typing import Any

from copilot_service.prompts import route_topic_prompt
from copilot_service.utils.json_extract import extract_json_value
from copilot_service.utils.validation import clamp_confidence


def build_prompt(task_input: dict[str, Any]) -> str:
    return route_topic_prompt(task_input)


def parse_output(raw_text: str | None, task_input: dict[str, Any], options: dict[str, Any]) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    fallback_on_invalid = options.get("fallback_on_invalid", True)
    fallback_key = task_input.get("fallback_key")

    try:
        payload = extract_json_value(raw_text or "")
        if not isinstance(payload, dict):
            raise ValueError("output must be a JSON object")

        topics = task_input.get("topics") or {}
        allowed = set(topics.keys())
        if fallback_key:
            allowed.add(str(fallback_key))

        decision = payload.get("decision")
        if not isinstance(decision, str) or decision not in allowed:
            raise ValueError("decision must be one of topic keys or fallback_key")

        reason = payload.get("reason")
        if not isinstance(reason, str):
            raise ValueError("reason must be a string")

        confidence = clamp_confidence(payload.get("confidence"))
        return True, {"decision": decision, "confidence": confidence, "reason": reason}, errors
    except ValueError as exc:
        errors.append({"code": "invalid_provider_output", "message": str(exc)})
        if fallback_on_invalid and isinstance(fallback_key, str) and fallback_key:
            return True, {
                "decision": fallback_key,
                "confidence": 0.0,
                "reason": "fallback due to invalid provider output",
            }, errors
        return False, {}, errors
