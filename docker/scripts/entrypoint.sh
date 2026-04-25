#!/usr/bin/env sh
set -eu

CONFIG_PATH="${NAGIENT_CONFIG:-/var/lib/nagient/config/config.toml}"
CONFIG_DIR="$(dirname "${CONFIG_PATH}")"
SECRETS_PATH="${NAGIENT_SECRETS_FILE:-/var/lib/nagient/secrets.env}"
SECRETS_DIR="$(dirname "${SECRETS_PATH}")"
TOOL_SECRETS_PATH="${NAGIENT_TOOL_SECRETS_FILE:-/var/lib/nagient/tool-secrets.env}"
TOOL_SECRETS_DIR="$(dirname "${TOOL_SECRETS_PATH}")"
PLUGINS_DIR="${NAGIENT_PLUGINS_DIR:-/var/lib/nagient/plugins}"
TOOLS_DIR="${NAGIENT_TOOLS_DIR:-/var/lib/nagient/tools}"
PROVIDERS_DIR="${NAGIENT_PROVIDERS_DIR:-/var/lib/nagient/providers}"
CREDENTIALS_DIR="${NAGIENT_CREDENTIALS_DIR:-/var/lib/nagient/credentials}"

mkdir -p "${CONFIG_DIR}" "${SECRETS_DIR}" "${TOOL_SECRETS_DIR}" "${PLUGINS_DIR}" "${TOOLS_DIR}" "${PROVIDERS_DIR}" "${CREDENTIALS_DIR}" "${NAGIENT_STATE_DIR:-/var/lib/nagient/state}" "${NAGIENT_LOG_DIR:-/var/lib/nagient/logs}" "${NAGIENT_RELEASES_DIR:-/var/lib/nagient/releases}"

if [ ! -f "${CONFIG_PATH}" ] && [ -f "/etc/nagient/config.toml" ]; then
  cp /etc/nagient/config.toml "${CONFIG_PATH}"
fi

if [ ! -f "${SECRETS_PATH}" ] && [ -f "/etc/nagient/secrets.env" ]; then
  cp /etc/nagient/secrets.env "${SECRETS_PATH}"
fi

if [ ! -f "${TOOL_SECRETS_PATH}" ] && [ -f "/etc/nagient/tool-secrets.env" ]; then
  cp /etc/nagient/tool-secrets.env "${TOOL_SECRETS_PATH}"
fi

if [ "${1:-}" = "nagient" ] && [ "${2:-}" = "serve" ]; then
  python -m nagient reconcile --format json >/tmp/nagient-reconcile.json
fi

exec "$@"
