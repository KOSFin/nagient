#!/usr/bin/env sh
set -eu

CONFIG_PATH="${NAGIENT_CONFIG:-/opt/nagient/config.toml}"
CONFIG_DIR="$(dirname "${CONFIG_PATH}")"
SECRETS_PATH="${NAGIENT_SECRETS_FILE:-/opt/nagient/secrets.env}"
SECRETS_DIR="$(dirname "${SECRETS_PATH}")"
TOOL_SECRETS_PATH="${NAGIENT_TOOL_SECRETS_FILE:-/opt/nagient/tool-secrets.env}"
TOOL_SECRETS_DIR="$(dirname "${TOOL_SECRETS_PATH}")"
PROMPTS_DIR="${NAGIENT_PROMPTS_DIR:-/opt/nagient/prompts}"
PLUGINS_DIR="${NAGIENT_PLUGINS_DIR:-/opt/nagient/plugins}"
TOOLS_DIR="${NAGIENT_TOOLS_DIR:-/opt/nagient/tools}"
PROVIDERS_DIR="${NAGIENT_PROVIDERS_DIR:-/opt/nagient/providers}"
CREDENTIALS_DIR="${NAGIENT_CREDENTIALS_DIR:-/opt/nagient/credentials}"
STATE_DIR="${NAGIENT_STATE_DIR:-/opt/nagient/state}"

mkdir -p "${CONFIG_DIR}" "${SECRETS_DIR}" "${TOOL_SECRETS_DIR}" "${PROMPTS_DIR}" "${PLUGINS_DIR}" "${TOOLS_DIR}" "${PROVIDERS_DIR}" "${CREDENTIALS_DIR}" "${STATE_DIR}" "${NAGIENT_LOG_DIR:-/opt/nagient/logs}" "${NAGIENT_RELEASES_DIR:-/opt/nagient/releases}"

if [ ! -f "${CONFIG_PATH}" ] && [ -f "/etc/nagient/config.toml" ]; then
  cp /etc/nagient/config.toml "${CONFIG_PATH}"
fi

if [ ! -f "${SECRETS_PATH}" ] && [ -f "/etc/nagient/secrets.env" ]; then
  cp /etc/nagient/secrets.env "${SECRETS_PATH}"
fi

if [ ! -f "${TOOL_SECRETS_PATH}" ] && [ -f "/etc/nagient/tool-secrets.env" ]; then
  cp /etc/nagient/tool-secrets.env "${TOOL_SECRETS_PATH}"
fi

if [ -n "${NAGIENT_PLUGIN_SPECS:-}" ]; then
  installed_specs="${STATE_DIR}/installed-plugin-specs"
  touch "${installed_specs}"
  old_ifs="${IFS}"
  IFS=','
  for plugin_spec in ${NAGIENT_PLUGIN_SPECS}; do
    plugin_spec="$(printf '%s' "${plugin_spec}" | sed 's/^ *//;s/ *$//')"
    [ -n "${plugin_spec}" ] || continue
    if grep -Fqx -- "${plugin_spec}" "${installed_specs}"; then
      continue
    fi
    if ! python -m nagient plugin install "${plugin_spec}"; then
      echo "nagient: failed to install configured plugin ${plugin_spec}" >&2
      exit 1
    fi
    printf '%s\n' "${plugin_spec}" >>"${installed_specs}"
  done
  IFS="${old_ifs}"
fi

if [ "${1:-}" = "nagient" ] && [ "${2:-}" = "serve" ]; then
  if ! python -m nagient reconcile --format json >/tmp/nagient-reconcile.json; then
    echo "nagient: reconcile reported blocked activation; continuing to serve for recovery." >&2
  fi
fi

exec "$@"
