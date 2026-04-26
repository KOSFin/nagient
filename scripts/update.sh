#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CHANNEL="__NAGIENT_DEFAULT_CHANNEL__"
DEFAULT_UPDATE_BASE_URL="__NAGIENT_UPDATE_BASE_URL__"

NAGIENT_CHANNEL="${NAGIENT_CHANNEL:-$DEFAULT_CHANNEL}"
NAGIENT_HOME="${NAGIENT_HOME:-$HOME/.nagient}"
NAGIENT_UPDATE_BASE_URL="${NAGIENT_UPDATE_BASE_URL:-${UPDATE_BASE_URL:-$DEFAULT_UPDATE_BASE_URL}}"
NAGIENT_COMPOSE_FILE="${NAGIENT_HOME}/docker-compose.yml"
NAGIENT_ENV_FILE="${NAGIENT_HOME}/.env"
NAGIENT_RELEASES_DIR="${NAGIENT_HOME}/releases"
CURRENT_MANIFEST="${NAGIENT_RELEASES_DIR}/current.json"

mkdir -p "${NAGIENT_HOME}/bin" "${NAGIENT_RELEASES_DIR}"

if [ "$NAGIENT_UPDATE_BASE_URL" = "__NAGIENT_UPDATE_BASE_URL__" ]; then
  echo "NAGIENT_UPDATE_BASE_URL is not configured." >&2
  echo "Use a rendered updater asset or export NAGIENT_UPDATE_BASE_URL/UPDATE_BASE_URL explicitly." >&2
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

write_nagientctl() {
  local target="${NAGIENT_HOME}/bin/nagientctl"
  cat >"$target" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

NAGIENT_HOME="${NAGIENT_HOME:-$HOME/.nagient}"
NAGIENT_COMPOSE_FILE="${NAGIENT_HOME}/docker-compose.yml"
NAGIENT_ENV_FILE="${NAGIENT_HOME}/.env"
NAGIENT_SERVICE="${NAGIENT_SERVICE:-nagient}"

usage() {
  cat <<'USAGE'
Usage: nagientctl <command>

Commands:
  up|start           Start runtime container
  down|stop          Stop runtime container
  restart            Restart runtime container
  status             Show container state and nagient status
  doctor             Show effective settings
  preflight          Run config validation
  reconcile          Run activation cycle
  logs [service]     Stream logs (default: nagient)
  shell              Open shell in runtime container
  exec <cmd...>      Execute command in runtime container
  update             Run installed updater
  remove|uninstall   Run installed uninstaller
  help               Show this help
USAGE
}

require_compose_files() {
  if [ ! -f "$NAGIENT_COMPOSE_FILE" ] || [ ! -f "$NAGIENT_ENV_FILE" ]; then
    echo "Nagient runtime is not initialized in $NAGIENT_HOME." >&2
    echo "Run install first: curl -fsSL https://ngnt-in.ruka.me/install.sh | bash" >&2
    exit 1
  fi
}

compose() {
  docker compose -f "$NAGIENT_COMPOSE_FILE" --env-file "$NAGIENT_ENV_FILE" "$@"
}

command_name="${1:-help}"
if [ "$#" -gt 0 ]; then
  shift
fi

case "$command_name" in
  up|start)
    require_compose_files
    compose up -d
    ;;
  down|stop)
    require_compose_files
    compose down --remove-orphans
    ;;
  restart)
    require_compose_files
    compose down --remove-orphans
    compose up -d
    ;;
  status)
    require_compose_files
    compose ps
    compose exec "$NAGIENT_SERVICE" nagient status --format text
    ;;
  doctor)
    require_compose_files
    compose exec "$NAGIENT_SERVICE" nagient doctor --format text
    ;;
  preflight)
    require_compose_files
    compose exec "$NAGIENT_SERVICE" nagient preflight --format text
    ;;
  reconcile)
    require_compose_files
    compose exec "$NAGIENT_SERVICE" nagient reconcile --format text
    ;;
  logs)
    require_compose_files
    if [ "$#" -eq 0 ]; then
      set -- "$NAGIENT_SERVICE"
    fi
    compose logs -f "$@"
    ;;
  shell)
    require_compose_files
    compose exec "$NAGIENT_SERVICE" sh
    ;;
  exec)
    require_compose_files
    if [ "$#" -eq 0 ]; then
      echo "Usage: nagientctl exec <cmd...>" >&2
      exit 1
    fi
    compose exec "$NAGIENT_SERVICE" "$@"
    ;;
  update)
    exec "${NAGIENT_HOME}/bin/nagient-update"
    ;;
  remove|uninstall)
    exec "${NAGIENT_HOME}/bin/nagient-uninstall"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: $command_name" >&2
    usage
    exit 1
    ;;
esac
EOF
  chmod +x "$target"
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
write_nagientctl

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
