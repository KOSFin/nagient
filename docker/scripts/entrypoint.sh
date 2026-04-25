#!/usr/bin/env sh
set -eu

CONFIG_PATH="${NAGIENT_CONFIG:-/var/lib/nagient/config/config.toml}"
CONFIG_DIR="$(dirname "${CONFIG_PATH}")"
SECRETS_PATH="${NAGIENT_SECRETS_FILE:-/var/lib/nagient/secrets.env}"
SECRETS_DIR="$(dirname "${SECRETS_PATH}")"
PLUGINS_DIR="${NAGIENT_PLUGINS_DIR:-/var/lib/nagient/plugins}"

mkdir -p "${CONFIG_DIR}" "${SECRETS_DIR}" "${PLUGINS_DIR}" "${NAGIENT_STATE_DIR:-/var/lib/nagient/state}" "${NAGIENT_LOG_DIR:-/var/lib/nagient/logs}" "${NAGIENT_RELEASES_DIR:-/var/lib/nagient/releases}"

if [ ! -f "${CONFIG_PATH}" ] && [ -f "/etc/nagient/config.toml" ]; then
  cp /etc/nagient/config.toml "${CONFIG_PATH}"
fi

if [ ! -f "${SECRETS_PATH}" ] && [ -f "/etc/nagient/secrets.env" ]; then
  cp /etc/nagient/secrets.env "${SECRETS_PATH}"
fi

if [ "${1:-}" = "nagient" ] && [ "${2:-}" = "serve" ]; then
  python -m nagient reconcile --format json >/tmp/nagient-reconcile.json
fi

exec "$@"
