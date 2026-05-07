"""Prompt templates for tasks."""

from __future__ import annotations

import json
from typing import Any


def route_topic_prompt(task_input: dict[str, Any]) -> str:
    schema = {
        "decision": "topic key string",
        "confidence": "number between 0 and 1",
        "reason": "short reason",
    }
    return (
        "You route an input to one topic key. Return JSON only.\\n"
        f"Allowed keys: {list(task_input.get('topics', {}).keys())} and fallback={task_input.get('fallback_key')}\\n"
        f"Output schema: {json.dumps(schema)}\\n"
        f"Input payload: {json.dumps(task_input, ensure_ascii=False)}"
    )


def freeform_prompt(task_input: dict[str, Any]) -> str:
    if "prompt" in task_input:
        return str(task_input["prompt"])
    return json.dumps(task_input, ensure_ascii=False)
