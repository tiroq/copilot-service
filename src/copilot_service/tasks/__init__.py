"""Task registry."""

from __future__ import annotations

from . import freeform, route_topic

TASKS = {
    "route-topic": route_topic,
    "freeform": freeform,
}
