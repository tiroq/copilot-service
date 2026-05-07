"""freeform task logic."""

from __future__ import annotations

from typing import Any

from copilot_service.prompts import freeform_prompt


def build_prompt(task_input: dict[str, Any]) -> str:
    return freeform_prompt(task_input)


def parse_output(raw_text: str | None, task_input: dict[str, Any], options: dict[str, Any]) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    return True, {"text": (raw_text or "").strip()}, []
