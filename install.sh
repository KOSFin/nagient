#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CHANNEL="stable"
DEFAULT_UPDATE_BASE_URL="https://ngnt-in.ruka.me"
UNRENDERED_UPDATE_BASE_URL_TOKEN="__NAGIENT_""UPDATE_BASE_URL__"

NAGIENT_CHANNEL="${NAGIENT_CHANNEL:-$DEFAULT_CHANNEL}"
NAGIENT_UPDATE_BASE_URL="${NAGIENT_UPDATE_BASE_URL:-${UPDATE_BASE_URL:-$DEFAULT_UPDATE_BASE_URL}}"

update_base_url_is_unrendered() {
  case "$1" in
    *"$UNRENDERED_UPDATE_BASE_URL_TOKEN"*) return 0 ;;
    *) return 1 ;;
  esac
}

if [ -z "$NAGIENT_UPDATE_BASE_URL" ] || {
  update_base_url_is_unrendered "$DEFAULT_UPDATE_BASE_URL" &&
  update_base_url_is_unrendered "$NAGIENT_UPDATE_BASE_URL"
}; then
  echo "NAGIENT_UPDATE_BASE_URL is not configured." >&2
  echo "This usually means the update center root is serving an unrendered bootstrap installer." >&2
  echo "Re-publish the update center or export NAGIENT_UPDATE_BASE_URL/UPDATE_BASE_URL explicitly." >&2
  exit 1
fi

fetch_url() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url"
    return 0
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO- "$url"
    return 0
  fi
  echo "Either curl or wget is required." >&2
  exit 1
}

extract_latest_version() {
  local payload_file="$1"
  tr -d '\n' <"$payload_file" | sed -n 's/.*"latest_version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p'
}

channel_payload="$(mktemp)"
trap 'rm -f "$channel_payload"' EXIT

fetch_url "${NAGIENT_UPDATE_BASE_URL%/}/channels/${NAGIENT_CHANNEL}.json" >"$channel_payload"
version="$(extract_latest_version "$channel_payload")"

if [ -z "$version" ]; then
  echo "Cannot resolve latest version for channel ${NAGIENT_CHANNEL}." >&2
  exit 1
fi

install_url="${NAGIENT_UPDATE_BASE_URL%/}/${version}/install.sh"
fetch_url "$install_url" | bash
