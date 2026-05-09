"""Service management commands (install / uninstall / status / restart / logs / test)."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

REPO_URL = "https://github.com/tiroq/copilot-service.git"
SERVICE_NAME = "copilot-service.service"

_REJECT_SUBSTRINGS = [
    "Install GitHub Copilot CLI?",
    "changed 2 packages",
    "unknown option",
    "unknown command",
]

_SMOKE_PAYLOAD: dict[str, Any] = {
    "task": "route-topic",
    "input": {
        "title": "Smoke test",
        "message": "",
        "article_excerpt": "Smoke test for copilot-service installation.",
        "topics": {
            "test": {
                "topic": "Test",
                "path": "test",
                "aliases": ["test", "smoke"],
            }
        },
        "fallback_key": "fallback",
    },
    "options": {"fallback_on_invalid": False},
}

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _info(msg: str) -> None:
    print(f"\033[1;34m[service]\033[0m {msg}", flush=True)


def _warn(msg: str) -> None:
    print(f"\033[1;33m[warn]\033[0m {msg}", file=sys.stderr, flush=True)


def _ok(msg: str) -> None:
    print(f"\033[1;32m[ok]\033[0m {msg}", flush=True)


def _err(msg: str) -> None:
    print(f"\033[1;31m[error]\033[0m {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Copilot CLI detection + validation
# ---------------------------------------------------------------------------


def validate_copilot_candidate(
    bin_path: str,
    model: str = "gpt-5-mini",
    timeout_seconds: int = 20,
) -> bool:
    """Return True if *bin_path* passes the non-interactive validation check."""
    p = Path(bin_path)
    if not p.is_file() or not os.access(bin_path, os.X_OK):
        return False

    argv = [
        bin_path,
        "-p",
        'Return only this exact JSON and nothing else: {"ok":true}',
        "--model",
        model,
        "--silent",
        "--no-color",
        "--no-auto-update",
        "--stream",
        "off",
        "--no-custom-instructions",
        "--no-ask-user",
        "--available-tools=",
    ]
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _warn(f"  candidate timed out ({timeout_seconds}s): {bin_path}")
        return False
    except OSError as exc:
        _warn(f"  candidate exec error: {bin_path}: {exc}")
        return False

    combined = result.stdout + result.stderr

    for bad in _REJECT_SUBSTRINGS:
        if bad in combined:
            _warn(f"  candidate rejected (contains {bad!r}): {bin_path}")
            return False

    if '"ok"' not in combined or "true" not in combined:
        _warn(f"  candidate did not return {{\"ok\":true}}: {bin_path}")
        _warn(f"  stdout: {result.stdout[:200]!r}")
        return False

    # Quick JSON parse check — look for {"ok": true} anywhere in output
    for line in combined.splitlines():
        stripped = line.strip().lstrip("● ").strip()
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and obj.get("ok") is True:
                return True
        except json.JSONDecodeError:
            pass
    _warn(f"  candidate output did not parse as {{\"ok\":true}}: {bin_path}")
    _warn(f"  stdout: {result.stdout[:200]!r}")
    return False


def detect_copilot_bin(
    explicit: str | None = None,
    model: str = "gpt-5-mini",
    timeout_seconds: int = 20,
) -> str | None:
    """
    Detect a working Copilot CLI binary.

    Order:
      1. *explicit* argument (--copilot-bin CLI flag)
      2. COPILOT_CLI env var
      3. ~/.local/bin/copilot
      4. ~/.vscode-server/.../copilotCli/copilot  (exact)
      5. ~/.vscode/.../copilotCli/copilot          (exact)
      6. find fallback under ~/.vscode-server and ~/.vscode
      7. command -v copilot (last resort)
    """
    home = Path.home()

    def _try(path: str, label: str) -> str | None:
        _info(f"Trying {label}: {path}")
        if validate_copilot_candidate(path, model=model, timeout_seconds=timeout_seconds):
            return path
        return None

    # 1. explicit
    if explicit:
        result = _try(explicit, "--copilot-bin")
        if result:
            return result
        raise SystemExit(f"[error] --copilot-bin '{explicit}' failed validation — aborting")

    # 2. env
    env_val = os.environ.get("COPILOT_CLI", "").strip()
    if env_val:
        result = _try(env_val, "COPILOT_CLI env")
        if result:
            return result
        raise SystemExit(f"[error] COPILOT_CLI='{env_val}' failed validation — aborting")

    # 3. ~/.local/bin/copilot
    local_bin = str(home / ".local" / "bin" / "copilot")
    if Path(local_bin).is_file():
        result = _try(local_bin, "~/.local/bin/copilot")
        if result:
            return result

    # 4. VS Code server exact
    vscode_server = str(
        home / ".vscode-server" / "data" / "User" / "globalStorage"
        / "github.copilot-chat" / "copilotCli" / "copilot"
    )
    if Path(vscode_server).is_file():
        result = _try(vscode_server, "vscode-server extension")
        if result:
            return result

    # 5. VS Code desktop exact
    vscode_local = str(
        home / ".vscode" / "data" / "User" / "globalStorage"
        / "github.copilot-chat" / "copilotCli" / "copilot"
    )
    if Path(vscode_local).is_file():
        result = _try(vscode_local, "vscode desktop extension")
        if result:
            return result

    # 6. find fallback
    for base in [home / ".vscode-server", home / ".vscode"]:
        if not base.is_dir():
            continue
        try:
            found = subprocess.run(
                ["find", str(base), "-type", "f",
                 "-path", "*/github.copilot-chat/copilotCli/copilot"],
                capture_output=True, text=True, timeout=10,
            )
            for candidate in found.stdout.splitlines():
                candidate = candidate.strip()
                if candidate and Path(candidate).is_file():
                    r = _try(candidate, f"find under {base.name}")
                    if r:
                        return r
        except (subprocess.TimeoutExpired, OSError):
            pass

    # 7. PATH
    path_bin = shutil.which("copilot")
    if path_bin:
        result = _try(path_bin, "PATH copilot")
        if result:
            return result
        _warn(f"PATH copilot at {path_bin} failed validation — skipping")

    return None


# ---------------------------------------------------------------------------
# Env file / unit file generation
# ---------------------------------------------------------------------------


def build_env_file(
    copilot_bin: str,
    model: str,
    timeout: int,
    host: str,
    port: int,
) -> str:
    """Return the contents of the environment file as a string."""
    return (
        f"COPILOT_SERVICE_PROVIDER=shell\n"
        f"COPILOT_SERVICE_SHELL_MODE=argv\n"
        f"COPILOT_SERVICE_SHELL_COMMAND={copilot_bin}\n"
        f"COPILOT_SERVICE_MODEL={model}\n"
        f"COPILOT_SERVICE_TIMEOUT_SECONDS={timeout}\n"
        f"COPILOT_SERVICE_HOST={host}\n"
        f"COPILOT_SERVICE_PORT={port}\n"
        f"NO_COLOR=1\n"
    )


def build_unit_file(
    install_dir: str,
    venv_dir: str,
    env_file: str,
    host: str,
    port: int,
) -> str:
    """Return the contents of the systemd user unit file as a string."""
    return (
        "[Unit]\n"
        "Description=Local Copilot Service REST wrapper\n"
        "After=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={install_dir}\n"
        f"EnvironmentFile={env_file}\n"
        f"ExecStart={venv_dir}/bin/copilot-service serve --host {host} --port {port}\n"
        "Restart=on-failure\n"
        "RestartSec=3\n"
        "TimeoutStopSec=10\n"
        "NoNewPrivileges=true\n"
        "PrivateTmp=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http_get(url: str, timeout: int = 5) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


def _http_post(url: str, payload: dict[str, Any], timeout: int = 60) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except Exception:  # noqa: BLE001
            body = {}
        return exc.code, body
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": str(exc)}


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def cmd_install(args: Any) -> int:  # noqa: C901
    home = Path.home()
    install_dir = Path(
        args.install_dir
        or os.environ.get("COPILOT_SERVICE_INSTALL_DIR", "")
        or str(home / ".local" / "share" / "copilot-service")
    )
    venv_dir = install_dir / ".venv"
    config_dir = home / ".config" / "copilot-service"
    env_file = config_dir / "env"
    systemd_dir = home / ".config" / "systemd" / "user"
    unit_file = systemd_dir / SERVICE_NAME

    host = args.host or os.environ.get("COPILOT_SERVICE_HOST", "127.0.0.1")
    port = int(args.port or os.environ.get("COPILOT_SERVICE_PORT", "8765"))
    model = args.model or os.environ.get("COPILOT_SERVICE_MODEL", "gpt-5-mini")
    timeout = int(args.timeout or os.environ.get("COPILOT_SERVICE_TIMEOUT_SECONDS", "90"))

    # --- Detect + validate Copilot CLI ---
    _info("Detecting Copilot CLI…")
    copilot_bin = detect_copilot_bin(
        explicit=getattr(args, "copilot_bin", None),
        model=model,
        timeout_seconds=20,
    )
    if not copilot_bin:
        _err(
            "No working Copilot CLI found.\n"
            "  Set COPILOT_CLI=/path/to/copilot or pass --copilot-bin and re-run."
        )
        return 1
    _ok(f"Validated Copilot CLI: {copilot_bin}")

    # --- Source dir / install ---
    source_dir: str | None = getattr(args, "source_dir", None)
    if not source_dir:
        # Try to detect repo root by looking for pyproject.toml relative to this file
        here = Path(__file__).resolve().parent.parent.parent
        if (here / "pyproject.toml").exists():
            source_dir = str(here)

    install_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    systemd_dir.mkdir(parents=True, exist_ok=True)

    # --- Create venv ---
    _info(f"Creating venv: {venv_dir}")
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
    )

    # --- Install package ---
    pip = str(venv_dir / "bin" / "pip")
    _info("Upgrading pip…")
    subprocess.run([pip, "install", "--upgrade", "pip", "-q"], check=True)

    if source_dir:
        _info(f"Installing package from source: {source_dir}")
        subprocess.run([pip, "install", "-e", source_dir, "-q"], check=True)
    else:
        _info(f"Installing package from git: {REPO_URL}")
        subprocess.run([pip, "install", f"git+{REPO_URL}", "-q"], check=True)

    # --- Write env file ---
    _info(f"Writing env file: {env_file}")
    env_contents = build_env_file(copilot_bin, model, timeout, host, port)
    env_file.write_text(env_contents, encoding="utf-8")
    env_file.chmod(0o600)

    # --- Write unit file ---
    _info(f"Writing unit file: {unit_file}")
    unit_contents = build_unit_file(
        str(install_dir), str(venv_dir), str(env_file), host, port
    )
    unit_file.write_text(unit_contents, encoding="utf-8")

    # --- systemctl ---
    _info("Reloading systemd user units…")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    _info("Enabling and starting service…")
    subprocess.run(
        ["systemctl", "--user", "enable", "--now", SERVICE_NAME],
        check=True,
    )

    # --- Health check ---
    _info("Waiting for service to start…")
    time.sleep(2)
    health_url = f"http://{host}:{port}/health"
    status, body = _http_get(health_url, timeout=5)
    if status != 200 or not body.get("ok"):
        _err(f"Health check failed (HTTP {status}): {body}")
        _err("Check: systemctl --user status copilot-service.service --no-pager")
        return 1
    _ok(f"Health check passed: {health_url}")

    # --- Smoke test ---
    skip_smoke = (
        getattr(args, "skip_provider_smoke", False)
        or os.environ.get("COPILOT_SERVICE_SKIP_PROVIDER_SMOKE", "") == "1"
    )
    if not skip_smoke:
        rc = _run_smoke_test(host, port)
        if rc != 0:
            return rc

    # --- Final message ---
    print()
    _ok("copilot-service installed and running.")
    print(f"  copilot-caas service status")
    print(f"  copilot-caas service logs")
    print(f"  copilot-caas service test")
    print(f"  curl -s http://{host}:{port}/health | jq .")
    print()
    print("For autostart after reboot (without active login session):")
    print(f"  sudo loginctl enable-linger \"$USER\"")
    return 0


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


def cmd_uninstall(args: Any) -> int:
    home = Path.home()
    install_dir = Path(
        args.install_dir
        or os.environ.get("COPILOT_SERVICE_INSTALL_DIR", "")
        or str(home / ".local" / "share" / "copilot-service")
    )
    config_dir = home / ".config" / "copilot-service"
    unit_file = home / ".config" / "systemd" / "user" / SERVICE_NAME

    remove_config = getattr(args, "remove_config", False)
    remove_install = getattr(args, "remove_install_dir", False)
    yes = getattr(args, "yes", False)

    if (remove_config or remove_install) and not yes:
        answer = input(
            f"This will permanently delete:\n"
            + (f"  {install_dir}\n" if remove_install else "")
            + (f"  {config_dir}\n" if remove_config else "")
            + "Continue? [y/N] "
        ).strip().lower()
        if answer != "y":
            print("Aborted.")
            return 0

    _info("Stopping and disabling service…")
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", SERVICE_NAME],
        check=False,
    )

    if unit_file.exists():
        unit_file.unlink()
        _info(f"Removed unit file: {unit_file}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    _ok("Systemd user service removed.")

    if remove_install:
        if install_dir.exists():
            shutil.rmtree(install_dir)
            _ok(f"Removed install dir: {install_dir}")
        else:
            _warn(f"Install dir not found: {install_dir}")

    if remove_config:
        if config_dir.exists():
            shutil.rmtree(config_dir)
            _ok(f"Removed config dir: {config_dir}")
        else:
            _warn(f"Config dir not found: {config_dir}")

    if not remove_install:
        _info(f"Install dir preserved: {install_dir}  (use --remove-install-dir to delete)")
    if not remove_config:
        _info(f"Config dir preserved: {config_dir}  (use --remove-config to delete)")

    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def cmd_status(args: Any) -> int:
    host = os.environ.get("COPILOT_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("COPILOT_SERVICE_PORT", "8765"))

    result = subprocess.run(
        ["systemctl", "--user", "status", SERVICE_NAME, "--no-pager"],
        check=False,
    )

    # Attempt health check if service appears active
    status, body = _http_get(f"http://{host}:{port}/health", timeout=3)
    if status == 200 and body.get("ok"):
        _ok(f"Health: http://{host}:{port}/health  →  {body.get('status', 'ok')}")
    elif status == 0:
        _warn("Service may not be listening — health check connection failed")

    return result.returncode


# ---------------------------------------------------------------------------
# restart
# ---------------------------------------------------------------------------


def cmd_restart(args: Any) -> int:
    host = os.environ.get("COPILOT_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("COPILOT_SERVICE_PORT", "8765"))

    _info("Restarting service…")
    result = subprocess.run(
        ["systemctl", "--user", "restart", SERVICE_NAME],
        check=False,
    )
    if result.returncode != 0:
        _err("systemctl restart failed")
        return result.returncode

    time.sleep(1)
    status, body = _http_get(f"http://{host}:{port}/health", timeout=5)
    if status == 200 and body.get("ok"):
        _ok(f"Service is up: http://{host}:{port}/health")
        return 0
    _err(f"Health check failed after restart (HTTP {status}): {body}")
    return 1


# ---------------------------------------------------------------------------
# logs
# ---------------------------------------------------------------------------


def cmd_logs(args: Any) -> int:
    lines = str(getattr(args, "lines", 120))
    follow = getattr(args, "follow", False)

    cmd = ["journalctl", "--user", "-u", SERVICE_NAME, "-n", lines]
    if not follow:
        cmd.append("--no-pager")
    else:
        cmd.append("-f")

    result = subprocess.run(cmd, check=False)
    return result.returncode


# ---------------------------------------------------------------------------
# test
# ---------------------------------------------------------------------------


def cmd_test(args: Any) -> int:  # noqa: C901
    home = Path.home()
    config_dir = home / ".config" / "copilot-service"
    env_file = config_dir / "env"
    host = os.environ.get("COPILOT_SERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("COPILOT_SERVICE_PORT", "8765"))

    rc = 0

    # --- Env file ---
    print(f"\n── Env file: {env_file}")
    if env_file.exists():
        print(env_file.read_text(encoding="utf-8"))
    else:
        _warn("Env file not found")

    # --- systemctl show ---
    print("── systemctl show")
    subprocess.run(
        [
            "systemctl", "--no-pager", "--user", "show", SERVICE_NAME,
            "-p", "EnvironmentFiles", "-p", "ExecStart",
        ],
        check=False,
    )

    # --- Health ---
    print("── GET /health")
    status, body = _http_get(f"http://{host}:{port}/health", timeout=5)
    if status == 200 and body.get("ok"):
        _ok(f"Health OK: {body}")
    else:
        _err(f"Health FAILED (HTTP {status}): {body}")
        rc = 1

    # --- Route-topic smoke ---
    print("── POST /v1/tasks/route-topic (smoke)")
    smoke_rc = _run_smoke_test(host, port, verbose=True)
    if smoke_rc != 0:
        rc = smoke_rc

    return rc


# ---------------------------------------------------------------------------
# shared smoke test helper
# ---------------------------------------------------------------------------


def _run_smoke_test(host: str, port: int, verbose: bool = False) -> int:
    url = f"http://{host}:{port}/v1/tasks/route-topic"
    _info(f"Running provider smoke test: POST {url}")
    status, body = _http_post(url, _SMOKE_PAYLOAD, timeout=60)

    if verbose:
        print(json.dumps(body, ensure_ascii=False, indent=2))

    if status == 0:
        _err(f"Smoke test: connection failed — {body.get('error', 'unknown')}")
        return 1

    errors = body.get("errors", [])
    has_invalid = any(e.get("code") == "invalid_provider_output" for e in errors)
    decision = (body.get("content") or {}).get("decision", "")
    reason = (body.get("content") or {}).get("reason", "")

    if has_invalid or reason == "fallback due to invalid provider output":
        _err("Smoke test FAILED: provider returned invalid output")
        if not verbose:
            print(json.dumps(body, ensure_ascii=False, indent=2))
        debug = (body.get("meta") or {}).get("provider_debug")
        if debug:
            _err(f"provider_debug: {debug}")
        return 1

    _ok(f"Smoke test passed: decision={decision!r}")
    debug = (body.get("meta") or {}).get("provider_debug")
    if debug:
        _info(f"provider_debug: {debug}")
    return 0
