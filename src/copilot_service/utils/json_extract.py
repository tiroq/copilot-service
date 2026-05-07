"""Robust JSON extraction from model output."""

from __future__ import annotations

import json
import re
from json import JSONDecodeError
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def extract_json_value(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty output")

    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    fence_match = _FENCE_RE.search(raw)
    if fence_match:
        parsed = _try_parse(fence_match.group(1).strip())
        if parsed is not None:
            return parsed

    parsed = _scan_for_json(raw)
    if parsed is not None:
        return parsed

    raise ValueError("no valid JSON found in provider output")


def _try_parse(candidate: str) -> Any | None:
    try:
        return json.loads(candidate)
    except JSONDecodeError:
        return None


def _scan_for_json(text: str) -> Any | None:
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(text[idx:])
        except JSONDecodeError:
            continue
        tail = text[idx + end :].strip()
        if not tail or "```" in text:
            return value
        if tail and not tail.startswith((".", ",", ";", ":")):
            return value
    return None
