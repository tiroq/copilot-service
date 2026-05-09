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

    # ── service subcommand group ──────────────────────────────────────────
    svc = sub.add_parser("service", help="Manage the local copilot-service systemd user service")
    svc_sub = svc.add_subparsers(dest="service_command")

    # install
    svc_install = svc_sub.add_parser("install", help="Install and start the systemd user service")
    svc_install.add_argument("--install-dir", default=None, help="Override install directory")
    svc_install.add_argument("--source-dir", default=None, help="Install from this local repo path")
    svc_install.add_argument("--copilot-bin", default=None, dest="copilot_bin", help="Path to Copilot CLI binary")
    svc_install.add_argument("--host", default=None)
    svc_install.add_argument("--port", default=None, type=int)
    svc_install.add_argument("--model", default=None)
    svc_install.add_argument("--timeout", default=None, type=int, dest="timeout")
    svc_install.add_argument("--skip-provider-smoke", action="store_true", default=False)

    # uninstall
    svc_uninstall = svc_sub.add_parser("uninstall", help="Stop and remove the systemd user service")
    svc_uninstall.add_argument("--install-dir", default=None, help="Override install directory")
    svc_uninstall.add_argument("--remove-config", action="store_true", default=False)
    svc_uninstall.add_argument("--remove-install-dir", action="store_true", default=False)
    svc_uninstall.add_argument("--yes", "-y", action="store_true", default=False, help="Skip confirmation")

    # status
    svc_sub.add_parser("status", help="Show service status and health")

    # restart
    svc_sub.add_parser("restart", help="Restart the service and verify health")

    # logs
    svc_logs = svc_sub.add_parser("logs", help="Show service journal logs")
    svc_logs.add_argument("-n", "--lines", type=int, default=120, help="Number of log lines")
    svc_logs.add_argument("-f", "--follow", action="store_true", default=False)

    # test
    svc_sub.add_parser("test", help="Run diagnostics and provider smoke test")

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

    if args.command == "service":
        # Import lazily to keep startup cost low for non-service paths
        from copilot_service import service as _svc  # noqa: PLC0415

        svc_cmd = getattr(args, "service_command", None)
        if svc_cmd == "install":
            return _svc.cmd_install(args)
        if svc_cmd == "uninstall":
            return _svc.cmd_uninstall(args)
        if svc_cmd == "status":
            return _svc.cmd_status(args)
        if svc_cmd == "restart":
            return _svc.cmd_restart(args)
        if svc_cmd == "logs":
            return _svc.cmd_logs(args)
        if svc_cmd == "test":
            return _svc.cmd_test(args)
        parser.parse_args(["service", "--help"])
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
