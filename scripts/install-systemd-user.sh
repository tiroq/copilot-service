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

# Validate a single copilot CLI candidate with a hard timeout.
# Returns 0 and prints the path if valid, 1 otherwise.
_validate_candidate() {
  local bin="$1"
  [[ -x "$bin" ]] || return 1

  local out
  # Run with a hard 20-second timeout; kill the process on expiry.
  out="$(timeout 20s "$bin" \
    -p 'Return only this exact JSON and nothing else: {"ok":true}' \
    --model "$MODEL" \
    --silent \
    --no-color \
    --no-auto-update \
    --stream off \
    --no-custom-instructions \
    --no-ask-user \
    --available-tools= \
    2>&1)" || {
      local rc=$?
      # timeout exits 124; any non-zero here means failure
      if [[ $rc -eq 124 ]]; then
        warn "  candidate timed out: $bin"
      else
        warn "  candidate exited $rc: $bin"
      fi
      return 1
    }

  # Reject output containing installer prompts or unknown-flag errors
  if echo "$out" | grep -qF 'Install GitHub Copilot CLI?'; then
    warn "  candidate shows installer prompt: $bin"
    return 1
  fi
  if echo "$out" | grep -qF 'changed 2 packages'; then
    warn "  candidate triggered npm install: $bin"
    return 1
  fi
  if echo "$out" | grep -qE 'unknown option|unknown command'; then
    warn "  candidate does not support required flags: $bin"
    return 1
  fi

  # Must contain {"ok": true} (with optional bullet prefix)
  if ! echo "$out" | grep -q '"ok"[[:space:]]*:[[:space:]]*true'; then
    warn "  candidate did not return {\"ok\":true}: $bin"
    warn "  output was: $(echo "$out" | head -3)"
    return 1
  fi

  printf '%s\n' "$bin"
  return 0
}

# Find and validate the Copilot CLI binary.
# Candidates tried in order:
#   1. $COPILOT_CLI env var
#   2. VS Code server extension path (exact)
#   3. VS Code local extension path (exact)
#   4. find fallback under ~/.vscode-server and ~/.vscode
#   5. command -v copilot (last resort)
detect_copilot_cli() {
  local candidate result

  # 1. Explicit override
  if [[ -n "${COPILOT_CLI:-}" ]]; then
    log "Trying COPILOT_CLI override: $COPILOT_CLI"
    result="$(_validate_candidate "$COPILOT_CLI")" && { printf '%s\n' "$result"; return 0; }
    fail "COPILOT_CLI was set to '$COPILOT_CLI' but validation failed — aborting"
  fi

  # 2. VS Code server extension (preferred)
  candidate="$HOME/.vscode-server/data/User/globalStorage/github.copilot-chat/copilotCli/copilot"
  if [[ -x "$candidate" ]]; then
    log "Trying VS Code server path: $candidate"
    result="$(_validate_candidate "$candidate")" && { printf '%s\n' "$result"; return 0; }
  fi

  # 3. VS Code local extension
  candidate="$HOME/.vscode/data/User/globalStorage/github.copilot-chat/copilotCli/copilot"
  if [[ -x "$candidate" ]]; then
    log "Trying VS Code local path: $candidate"
    result="$(_validate_candidate "$candidate")" && { printf '%s\n' "$result"; return 0; }
  fi

  # 4. find fallback under both vscode dirs
  while IFS= read -r candidate; do
    [[ -x "$candidate" ]] || continue
    log "Trying found path: $candidate"
    result="$(_validate_candidate "$candidate")" && { printf '%s\n' "$result"; return 0; }
  done < <(find "$HOME/.vscode-server" "$HOME/.vscode" \
    -type f \
    -path '*/github.copilot-chat/copilotCli/copilot' \
    2>/dev/null || true)

  # 5. PATH last resort — only accept if it validates cleanly
  if command -v copilot >/dev/null 2>&1; then
    candidate="$(command -v copilot)"
    log "Trying PATH copilot: $candidate"
    result="$(_validate_candidate "$candidate")" && { printf '%s\n' "$result"; return 0; }
    warn "PATH copilot at $candidate failed validation (installer prompt or bad output) — skipping"
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
  fail "No working Copilot CLI found. Set COPILOT_CLI=/path/to/copilot and re-run, or check 'journalctl --user -u copilot-service.service'"
fi

log "Validated Copilot CLI: $COPILOT_BIN"

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