"""Robust JSON extraction from model output."""

from __future__ import annotations

import json
import re
from json import JSONDecodeError
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)

# Matches raw (unescaped) control characters inside JSON string spans that
# would cause json.loads to reject otherwise valid LLM output.
# Strategy: replace bare newlines/tabs inside JSON strings with their
# escaped equivalents so the decoder accepts them.
_RAW_NEWLINE_IN_STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"', re.DOTALL)


def _escape_raw_control_chars(text: str) -> str:
    """Replace literal newlines/tabs inside JSON string literals with escape sequences."""
    def _fix_string(m: re.Match) -> str:
        s = m.group(0)
        # Replace bare newlines and tabs inside the string (not already escaped)
        s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return s
    return _RAW_NEWLINE_IN_STRING_RE.sub(_fix_string, text)


def extract_json_value(text: str) -> Any:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty output")

    # Pass 1: direct parse
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    # Pass 2: fenced code block
    fence_match = _FENCE_RE.search(raw)
    if fence_match:
        parsed = _try_parse(fence_match.group(1).strip())
        if parsed is not None:
            return parsed

    # Pass 3: scan for first JSON object/array
    parsed = _scan_for_json(raw)
    if parsed is not None:
        return parsed

    # Pass 4: retry scan after escaping raw control chars in strings
    # (handles LLM output with literal newlines inside JSON string values)
    sanitized = _escape_raw_control_chars(raw)
    if sanitized != raw:
        parsed = _scan_for_json(sanitized)
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
    return None
