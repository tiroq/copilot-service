#!/usr/bin/env bash
# Uninstall copilot-service systemd user service.
#
# If the package is installed, the preferred interface is:
#   copilot-caas service uninstall [flags]
#
# Delegate to the CLI if available:
if command -v copilot-caas >/dev/null 2>&1; then
  exec copilot-caas service uninstall "$@"
fi

set -euo pipefail

INSTALL_DIR="${COPILOT_SERVICE_INSTALL_DIR:-$HOME/.local/share/copilot-service}"
CONFIG_DIR="$HOME/.config/copilot-service"
UNIT_FILE="$HOME/.config/systemd/user/copilot-service.service"

systemctl --user disable --now copilot-service.service 2>/dev/null || true
rm -f "$UNIT_FILE"
systemctl --user daemon-reload

echo "Removed systemd user service."

read -r -p "Remove install dir $INSTALL_DIR? [y/N] " remove_install
if [[ "$remove_install" == "y" || "$remove_install" == "Y" ]]; then
  rm -rf "$INSTALL_DIR"
  echo "Removed $INSTALL_DIR"
fi

read -r -p "Remove config dir $CONFIG_DIR? [y/N] " remove_config
if [[ "$remove_config" == "y" || "$remove_config" == "Y" ]]; then
  rm -rf "$CONFIG_DIR"
  echo "Removed $CONFIG_DIR"
fi