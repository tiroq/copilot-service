"""Lightweight terminal formatting helpers using ANSI escape codes only.

Color is disabled when:
- NO_COLOR environment variable is set (any value), per https://no-color.org/
- the target stream is not a TTY
- ``color_enabled=False`` is passed explicitly
"""

from __future__ import annotations

import os
import sys


def supports_color(stream=None) -> bool:
    """Return True if ``stream`` (default stdout) supports ANSI colors."""
    if stream is None:
        stream = sys.stdout
    if os.environ.get("NO_COLOR") is not None:
        return False
    if not hasattr(stream, "isatty"):
        return False
    return stream.isatty()


def _ansi(code: str, text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"


def color(text: str, code: str, enabled: bool = True) -> str:
    return _ansi(code, text, enabled)


def bold(text: str, enabled: bool = True) -> str:
    return _ansi("1", text, enabled)


def dim(text: str, enabled: bool = True) -> str:
    return _ansi("2", text, enabled)


def cyan(text: str, enabled: bool = True) -> str:
    return _ansi("36", text, enabled)


def magenta(text: str, enabled: bool = True) -> str:
    return _ansi("35", text, enabled)


def green(text: str, enabled: bool = True) -> str:
    return _ansi("32", text, enabled)


def yellow(text: str, enabled: bool = True) -> str:
    return _ansi("33", text, enabled)


def blue(text: str, enabled: bool = True) -> str:
    return _ansi("34", text, enabled)


def render_welcome(version: str, color_enabled: bool = True) -> str:
    """Return the no-args welcome screen as a string."""
    c = color_enabled

    inner = f"  \u2756 Copilot CaaS {version}  "
    sub = "  Local Copilot backend for scripts & agents  "
    width = max(len(inner), len(sub))

    border_top = cyan("\u256d" + "\u2500" * (width + 2) + "\u256e", c)
    row1 = cyan("\u2502", c) + bold(cyan(inner.ljust(width + 2), c), c) + cyan("\u2502", c)
    row2 = cyan("\u2502", c) + dim(sub.ljust(width + 2), c) + cyan("\u2502", c)
    border_bot = cyan("\u2570" + "\u2500" * (width + 2) + "\u2574", c)

    lines = [
        border_top,
        row1,
        row2,
        border_bot,
        "",
        bold("Usage:", c),
        f"  {cyan('copilot-caas', c)} ask --input request.json",
        f"  cat request.json | {cyan('copilot-caas', c)} ask --stdin",
        f"  {cyan('copilot-caas', c)} serve --host 127.0.0.1 --port 8765",
        "",
        bold("Commands:", c),
        f"  {green('ask', c)}      Run a task through the configured provider",
        f"  {green('serve', c)}    Start local REST API server",
        "",
        bold("Providers:", c),
        f"  {yellow('COPILOT_SERVICE_PROVIDER', c)}=shell",
        f"  {yellow('COPILOT_SERVICE_SHELL_COMMAND', c)}=\"<your copilot command>\"",
        "",
        bold("Examples:", c),
        f"  export {yellow('COPILOT_SERVICE_PROVIDER', c)}=fake",
        f"  {cyan('copilot-caas', c)} ask --input examples/route-topic-request.json",
        "",
        bold("Docs:", c),
        f"  {dim('https://github.com/tiroq/copilot-service', c)}",
        "",
    ]
    return "\n".join(lines)
