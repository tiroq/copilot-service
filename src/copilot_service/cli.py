"""CLI entrypoint for copilot-service."""

from __future__ import annotations

import argparse
import json
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from typing import Any

from copilot_service.config import ServiceConfig
from copilot_service.runner import run_bridge_request
from copilot_service.server import run_server
from copilot_service.terminal import render_welcome, supports_color


def _get_version() -> str:
    try:
        return _pkg_version("copilot-caas")
    except PackageNotFoundError:
        return "0.0.0-dev"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copilot-caas",
        description="Local Copilot backend for scripts & agents.",
        add_help=True,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"copilot-caas {_get_version()}",
    )
    sub = parser.add_subparsers(dest="command")

    ask = sub.add_parser("ask", help="Run a task through the configured provider")
    ask.add_argument("--input", dest="input_file", help="Path to request JSON")
    ask.add_argument("--stdin", action="store_true", help="Read request JSON from stdin")
    ask.add_argument("--task", help="Task name (for direct invocation)")
    ask.add_argument("--prompt", help="Prompt text (for freeform)")

    serve = sub.add_parser("serve", help="Start local REST API server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", default=None, type=int)
    return parser


def _load_request(args: argparse.Namespace) -> dict[str, object]:
    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as fh:
            return json.load(fh)
    if args.stdin:
        return json.loads(sys.stdin.read() or "{}")
    if args.task:
        if args.task == "freeform":
            return {
                "task": "freeform",
                "input": {"prompt": args.prompt or ""},
                "options": {},
            }
        return {"task": args.task, "input": {}, "options": {}}
    raise SystemExit("Provide --input, --stdin, or --task")


def _cli_error_response(message: str, provider: str, model: str) -> dict[str, Any]:
    return {
        "ok": False,
        "task": "",
        "provider": provider,
        "model": model,
        "content": {},
        "raw_text": None,
        "errors": [{"code": "invalid_request", "message": message}],
        "meta": {"duration_ms": 0, "attempts": 1},
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # No subcommand: show welcome screen and exit 0
    if not args.command:
        print(render_welcome(_get_version(), color_enabled=supports_color(sys.stdout)))
        return 0

    if args.command == "serve":
        cfg = ServiceConfig.from_env()
        if args.host:
            cfg.host = args.host
        if args.port:
            cfg.port = args.port
        run_server(cfg)
        return 0

    cfg = ServiceConfig.from_env()
    try:
        request = _load_request(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        response = _cli_error_response(str(exc), provider=cfg.provider, model=cfg.model)
        print(json.dumps(response, ensure_ascii=False))
        return 2

    response = run_bridge_request(request, config=cfg)
    print(json.dumps(response, ensure_ascii=False))
    return 0 if response.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
