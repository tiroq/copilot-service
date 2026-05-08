#!/usr/bin/env bash
set -euo pipefail

APP_NAME="copilot-service"
REPO_URL="https://github.com/tiroq/copilot-service.git"

INSTALL_DIR="${COPILOT_SERVICE_INSTALL_DIR:-$HOME/.local/share/copilot-service}"
VENV_DIR="$INSTALL_DIR/.venv"
CONFIG_DIR="$HOME/.config/copilot-service"
ENV_FILE="$CONFIG_DIR/env"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
UNIT_FILE="$SYSTEMD_USER_DIR/copilot-service.service"

HOST="${COPILOT_SERVICE_HOST:-127.0.0.1}"
PORT="${COPILOT_SERVICE_PORT:-8765}"
MODEL="${COPILOT_SERVICE_MODEL:-gpt-5-mini}"
TIMEOUT="${COPILOT_SERVICE_TIMEOUT_SECONDS:-90}"

log() {
  printf '\033[1;34m[install]\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2
}

fail() {
  printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2
  exit 1
}

detect_copilot_cli() {
  if [[ -n "${COPILOT_CLI:-}" && -x "${COPILOT_CLI}" ]]; then
    printf '%s\n' "$COPILOT_CLI"
    return 0
  fi

  local vscode_cli
  vscode_cli="$(find "$HOME/.vscode-server" "$HOME/.vscode" \
    -type f \
    -path '*/github.copilot-chat/copilotCli/copilot' \
    2>/dev/null \
    | head -n 1 || true)"

  if [[ -n "$vscode_cli" && -x "$vscode_cli" ]]; then
    printf '%s\n' "$vscode_cli"
    return 0
  fi

  if command -v copilot >/dev/null 2>&1; then
    command -v copilot
    return 0
  fi

  return 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

need_cmd git
need_cmd python3
need_cmd systemctl
need_cmd curl

if ! python3 - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  fail "Python 3.11+ is required"
fi

COPILOT_BIN="$(detect_copilot_cli || true)"
if [[ -z "$COPILOT_BIN" ]]; then
  fail "Copilot CLI not found. Run with COPILOT_CLI=/path/to/copilot $0"
fi

log "Using Copilot CLI: $COPILOT_BIN"

log "Checking Copilot CLI non-interactive mode"

if ! "$COPILOT_BIN" \
  --model "$MODEL" \
  -p 'Return only this exact JSON and nothing else: {"ok":true}' \
  --silent \
  --no-color \
  --no-auto-update \
  --stream off \
  --no-custom-instructions \
  --no-ask-user \
  --available-tools= \
  | grep -q '"ok"[[:space:]]*:[[:space:]]*true'
then
  fail "Copilot CLI non-interactive check failed"
fi

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$SYSTEMD_USER_DIR"

if [[ -d "$INSTALL_DIR/.git" ]]; then
  log "Updating existing repo: $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only
else
  log "Cloning repo into: $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

log "Creating virtualenv"
python3 -m venv "$VENV_DIR"

log "Installing package"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$INSTALL_DIR"

log "Writing env file: $ENV_FILE"
cat > "$ENV_FILE" <<EOF
COPILOT_SERVICE_PROVIDER=shell
COPILOT_SERVICE_SHELL_MODE=argv
COPILOT_SERVICE_SHELL_COMMAND=$COPILOT_BIN
COPILOT_SERVICE_MODEL=$MODEL
COPILOT_SERVICE_TIMEOUT_SECONDS=$TIMEOUT
COPILOT_SERVICE_HOST=$HOST
COPILOT_SERVICE_PORT=$PORT
NO_COLOR=1
EOF

chmod 600 "$ENV_FILE"

log "Writing systemd user unit: $UNIT_FILE"
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Local Copilot Service REST wrapper
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/copilot-service serve --host $HOST --port $PORT
Restart=on-failure
RestartSec=3
TimeoutStopSec=10

# Basic hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
EOF

log "Reloading systemd user units"
systemctl --user daemon-reload

log "Enabling and starting service"
systemctl --user enable --now copilot-service.service

log "Checking health"
sleep 1
curl -fsS "http://$HOST:$PORT/health" >/dev/null || {
  systemctl --user status copilot-service.service --no-pager || true
  fail "Service started but healthcheck failed"
}

if [[ "${COPILOT_SERVICE_SKIP_PROVIDER_SMOKE:-0}" != "1" ]]; then
  log "Running route-topic smoke test"
  _smoke_payload=$(mktemp)
  cat > "$_smoke_payload" <<'PAYLOAD'
{
  "task": "route-topic",
  "input": {
    "title": "Smoke test",
    "message": "",
    "article_excerpt": "Smoke test for copilot-service installation.",
    "topics": {
      "test": {
        "topic": "Test",
        "path": "test",
        "aliases": ["test", "smoke"]
      }
    },
    "fallback_key": "fallback"
  },
  "options": {"fallback_on_invalid": false}
}
PAYLOAD
  _smoke_out=$(curl -sS "http://$HOST:$PORT/v1/tasks/route-topic" \
    -H 'Content-Type: application/json' \
    --data-binary "@$_smoke_payload" 2>&1) || true
  rm -f "$_smoke_payload"

  if echo "$_smoke_out" | grep -q '"invalid_provider_output"'; then
    warn "route-topic smoke test detected invalid_provider_output"
    warn "Response: $_smoke_out"
    warn "Check: cat $ENV_FILE"
    warn "Check: journalctl --user -u copilot-service.service -n 40 --no-pager"
    fail "Provider smoke test failed — shell provider returned invalid output"
  fi
  log "Smoke test passed"
fi

log "OK: copilot-service is running at http://$HOST:$PORT"
log "Try: curl -sS http://$HOST:$PORT/health"