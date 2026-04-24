#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CHANNEL="__NAGIENT_DEFAULT_CHANNEL__"
DEFAULT_UPDATE_BASE_URL="__NAGIENT_UPDATE_BASE_URL__"

NAGIENT_CHANNEL="${NAGIENT_CHANNEL:-$DEFAULT_CHANNEL}"
NAGIENT_HOME="${NAGIENT_HOME:-$HOME/.nagient}"
NAGIENT_UPDATE_BASE_URL="${NAGIENT_UPDATE_BASE_URL:-$DEFAULT_UPDATE_BASE_URL}"
NAGIENT_COMPOSE_FILE="${NAGIENT_HOME}/docker-compose.yml"
NAGIENT_ENV_FILE="${NAGIENT_HOME}/.env"
NAGIENT_RELEASES_DIR="${NAGIENT_HOME}/releases"
CURRENT_MANIFEST="${NAGIENT_RELEASES_DIR}/current.json"

mkdir -p "${NAGIENT_HOME}/bin" "${NAGIENT_RELEASES_DIR}"

if [ "$NAGIENT_UPDATE_BASE_URL" = "__NAGIENT_UPDATE_BASE_URL__" ]; then
  echo "NAGIENT_UPDATE_BASE_URL is not configured." >&2
  echo "Use a released updater asset or export NAGIENT_UPDATE_BASE_URL explicitly." >&2
  exit 1
fi

if [ "$NAGIENT_CHANNEL" = "__NAGIENT_DEFAULT_CHANNEL__" ]; then
  NAGIENT_CHANNEL="stable"
fi

if [ ! -f "$CURRENT_MANIFEST" ]; then
  echo "Current installation metadata is missing. Run install.sh first." >&2
  exit 1
fi

python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  echo "python"
}

fetch_url() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url"
    return 0
  fi
  wget -qO- "$url"
}

json_field() {
  local field="$1"
  local payload_file="$2"
  "$(python_cmd)" - "$field" "$payload_file" <<'PY'
import json
import sys

field = sys.argv[1].split(".")
payload = json.loads(open(sys.argv[2], "r", encoding="utf-8").read())
current = payload
for chunk in field:
    current = current[chunk]
print(current)
PY
}

artifact_url() {
  local artifact_name="$1"
  local payload_file="$2"
  "$(python_cmd)" - "$artifact_name" "$payload_file" <<'PY'
import json
import sys

artifact_name = sys.argv[1]
payload = json.loads(open(sys.argv[2], "r", encoding="utf-8").read())
for artifact in payload.get("artifacts", []):
    if artifact.get("name") == artifact_name:
        print(artifact["url"])
        sys.exit(0)
raise SystemExit(f"Artifact not found: {artifact_name}")
PY
}

channel_payload="$(mktemp)"
manifest_payload="$(mktemp)"
trap 'rm -f "$channel_payload" "$manifest_payload"' EXIT

current_version="$(json_field version "$CURRENT_MANIFEST")"
fetch_url "${NAGIENT_UPDATE_BASE_URL%/}/channels/${NAGIENT_CHANNEL}.json" >"$channel_payload"
manifest_url="$(json_field manifest_url "$channel_payload")"
fetch_url "$manifest_url" >"$manifest_payload"
target_version="$(json_field version "$manifest_payload")"

if [ "$current_version" = "$target_version" ]; then
  echo "Nagient is already on ${current_version}"
  exit 0
fi

compose_url="$(json_field docker.compose_url "$manifest_payload")"
image="$(json_field docker.image "$manifest_payload")"
update_url="$(artifact_url update.sh "$manifest_payload")"
uninstall_url="$(artifact_url uninstall.sh "$manifest_payload")"
fetch_url "$compose_url" >"$NAGIENT_COMPOSE_FILE"
cp "$manifest_payload" "$CURRENT_MANIFEST"
cp "$manifest_payload" "${NAGIENT_RELEASES_DIR}/${target_version}.json"
fetch_url "$update_url" >"${NAGIENT_HOME}/bin/nagient-update"
fetch_url "$uninstall_url" >"${NAGIENT_HOME}/bin/nagient-uninstall"
chmod +x "${NAGIENT_HOME}/bin/nagient-update" "${NAGIENT_HOME}/bin/nagient-uninstall"

cat >"$NAGIENT_ENV_FILE" <<EOF
NAGIENT_IMAGE=${image}
NAGIENT_CHANNEL=${NAGIENT_CHANNEL}
NAGIENT_UPDATE_BASE_URL=${NAGIENT_UPDATE_BASE_URL}
NAGIENT_CONTAINER_NAME=nagient
NAGIENT_DOCKER_PROJECT_NAME=nagient
EOF

docker compose -f "$NAGIENT_COMPOSE_FILE" --env-file "$NAGIENT_ENV_FILE" pull
docker compose -f "$NAGIENT_COMPOSE_FILE" --env-file "$NAGIENT_ENV_FILE" up -d

echo "Nagient upgraded: ${current_version} -> ${target_version}"
