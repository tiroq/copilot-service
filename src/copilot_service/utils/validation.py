"""Validation helpers."""

from __future__ import annotations


def clamp_confidence(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number
