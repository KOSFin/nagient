#!/usr/bin/env sh
set -eu

CONFIG_PATH="${NAGIENT_CONFIG:-/var/lib/nagient/config/config.toml}"
CONFIG_DIR="$(dirname "${CONFIG_PATH}")"

mkdir -p "${CONFIG_DIR}" "${NAGIENT_STATE_DIR:-/var/lib/nagient/state}" "${NAGIENT_LOG_DIR:-/var/lib/nagient/logs}" "${NAGIENT_RELEASES_DIR:-/var/lib/nagient/releases}"

if [ ! -f "${CONFIG_PATH}" ] && [ -f "/etc/nagient/config.toml" ]; then
  cp /etc/nagient/config.toml "${CONFIG_PATH}"
fi

exec "$@"

