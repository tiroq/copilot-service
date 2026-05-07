"""Minimal logging helpers."""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    return logging.getLogger(name)
