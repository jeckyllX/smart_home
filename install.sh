#!/usr/bin/env bash
#
# Install the Smart Home daemon as a systemd user service.
#
# Renders smart_home.service with the absolute path of the directory this
# script lives in, installs it under ~/.config/systemd/user, and enables it.

set -euo pipefail

UNIT_NAME="smart_home.service"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
UNIT_SRC="${PROJECT_DIR}/${UNIT_NAME}"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
UNIT_DST="${UNIT_DIR}/${UNIT_NAME}"
CLI="${PROJECT_DIR}/.venv/bin/smarthome"

if [[ ! -x "${CLI}" ]]; then
    echo "error: ${CLI} not found." >&2
    echo "Set up the environment first:" >&2
    echo "  python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
    exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
    echo "error: systemctl not found; this installer targets systemd." >&2
    exit 1
fi

escape_replacement() {
    # Escape characters sed treats specially in the replacement string.
    printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'
}

mkdir -p "${UNIT_DIR}"
sed "s|__PROJECT_DIR__|$(escape_replacement "${PROJECT_DIR}")|g" "${UNIT_SRC}" > "${UNIT_DST}"

systemctl --user daemon-reload
systemctl --user enable --now "${UNIT_NAME}"

echo "Installed ${UNIT_DST} (running from ${PROJECT_DIR})"
echo "Logs: journalctl --user -u ${UNIT_NAME} -f"
