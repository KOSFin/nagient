#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CHANNEL="__NAGIENT_DEFAULT_CHANNEL__"
DEFAULT_UPDATE_BASE_URL="__NAGIENT_UPDATE_BASE_URL__"
UNRENDERED_UPDATE_BASE_URL_TOKEN="__NAGIENT_""UPDATE_BASE_URL__"

NAGIENT_CHANNEL="${NAGIENT_CHANNEL:-$DEFAULT_CHANNEL}"
NAGIENT_HOME="${NAGIENT_HOME:-$HOME/.nagient}"
NAGIENT_UPDATE_BASE_URL="${NAGIENT_UPDATE_BASE_URL:-${UPDATE_BASE_URL:-$DEFAULT_UPDATE_BASE_URL}}"
NAGIENT_COMPOSE_FILE="${NAGIENT_HOME}/docker-compose.yml"
NAGIENT_ENV_FILE="${NAGIENT_HOME}/.env"
NAGIENT_RELEASES_DIR="${NAGIENT_HOME}/releases"
CURRENT_MANIFEST="${NAGIENT_RELEASES_DIR}/current.json"

mkdir -p "${NAGIENT_HOME}/bin" "${NAGIENT_RELEASES_DIR}"

log_step() {
  printf '[nagient] %s\n' "$1"
}

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
  cat >"$target" <<'NAGIENTCTL'
#!/usr/bin/env bash
set -euo pipefail

PROGRAM_NAME="$(basename "$0")"
NAGIENT_HOME="${NAGIENT_HOME:-$HOME/.nagient}"
NAGIENT_COMPOSE_FILE="${NAGIENT_HOME}/docker-compose.yml"
NAGIENT_ENV_FILE="${NAGIENT_HOME}/.env"
NAGIENT_SERVICE="${NAGIENT_SERVICE:-nagient}"
NAGIENT_CONFIG_FILE="${NAGIENT_HOME}/config.toml"
NAGIENT_SECRETS_FILE="${NAGIENT_HOME}/secrets.env"
NAGIENT_TOOL_SECRETS_FILE="${NAGIENT_HOME}/tool-secrets.env"
NAGIENT_WORKSPACE_DIR="${NAGIENT_HOME}/workspace"
NAGIENT_LOG_DIR="${NAGIENT_HOME}/logs"

usage() {
  cat <<USAGE
Usage: ${PROGRAM_NAME} <command>

Commands:
  status|st          Show compact runtime status
  doctor|cfg         Show detailed runtime diagnostics
  paths|config       Show local config and workspace paths
  ps                 Show raw docker compose status
  up|start           Start runtime container
  down|stop          Stop runtime container
  restart            Restart runtime container
  preflight|check    Run config validation
  reconcile|fix      Run activation cycle
  logs|log [svc]     Stream logs (default: nagient)
  shell|sh           Open shell in runtime container
  exec|x <cmd...>    Execute command in runtime container
  update             Run installed updater
  remove|uninstall   Run installed uninstaller
  help               Show this help
  <other command>    Pass through to the in-container nagient CLI
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

compose_exec() {
  compose exec \
    -e "NAGIENT_HOST_HOME=$NAGIENT_HOME" \
    -e "NAGIENT_HOST_CONFIG_FILE=$NAGIENT_CONFIG_FILE" \
    -e "NAGIENT_HOST_SECRETS_FILE=$NAGIENT_SECRETS_FILE" \
    -e "NAGIENT_HOST_TOOL_SECRETS_FILE=$NAGIENT_TOOL_SECRETS_FILE" \
    -e "NAGIENT_HOST_WORKSPACE_DIR=$NAGIENT_WORKSPACE_DIR" \
    "$NAGIENT_SERVICE" "$@"
}

print_paths() {
  cat <<EOF
Nagient home: $NAGIENT_HOME
Config: $NAGIENT_CONFIG_FILE
Secrets: $NAGIENT_SECRETS_FILE
Tool secrets: $NAGIENT_TOOL_SECRETS_FILE
Workspace: $NAGIENT_WORKSPACE_DIR
Logs: $NAGIENT_LOG_DIR
EOF
}

command_name="${1:-help}"
if [ "$#" -gt 0 ]; then
  shift
fi

case "$command_name" in
  status|st)
    require_compose_files
    compose_exec nagient status --format text "$@"
    ;;
  doctor|cfg)
    require_compose_files
    compose_exec nagient doctor --format text "$@"
    ;;
  paths|config)
    print_paths
    ;;
  ps)
    require_compose_files
    compose ps
    ;;
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
  preflight|check)
    require_compose_files
    compose_exec nagient preflight --format text "$@"
    ;;
  reconcile|fix)
    require_compose_files
    compose_exec nagient reconcile --format text "$@"
    ;;
  logs|log)
    require_compose_files
    if [ "$#" -eq 0 ]; then
      set -- "$NAGIENT_SERVICE"
    fi
    compose logs -f "$@"
    ;;
  shell|sh)
    require_compose_files
    compose exec "$NAGIENT_SERVICE" sh
    ;;
  exec|x)
    require_compose_files
    if [ "$#" -eq 0 ]; then
      echo "Usage: ${PROGRAM_NAME} exec <cmd...>" >&2
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
    require_compose_files
    compose_exec nagient "$command_name" "$@"
    ;;
esac
NAGIENTCTL
  chmod +x "$target"
  cp "$target" "${NAGIENT_HOME}/bin/nagient"
  chmod +x "${NAGIENT_HOME}/bin/nagient"
}

run_compose_update_step() {
  local log_file
  local output=""
  log_file="$(mktemp)"
  if ! docker compose -f "$NAGIENT_COMPOSE_FILE" --env-file "$NAGIENT_ENV_FILE" "$@" 2>&1 | tee "$log_file"; then
    output="$(cat "$log_file")"
    rm -f "$log_file"
    case "$output" in
      *"no matching manifest"*arm64*|*"no matching manifest"*linux/arm64*)
        echo "The published Docker image does not include an arm64 variant yet." >&2
        echo "Temporary workaround on Apple Silicon:" >&2
        echo "DOCKER_DEFAULT_PLATFORM=linux/amd64 ~/.nagient/bin/nagient-update" >&2
        ;;
    esac
    exit 1
  fi
  rm -f "$log_file"
}

channel_payload="$(mktemp)"
manifest_payload="$(mktemp)"
trap 'rm -f "$channel_payload" "$manifest_payload"' EXIT

current_version="$(json_field version "$CURRENT_MANIFEST")"
log_step "Resolving update channel metadata"
fetch_url "${NAGIENT_UPDATE_BASE_URL%/}/channels/${NAGIENT_CHANNEL}.json" >"$channel_payload"
manifest_url="$(json_field manifest_url "$channel_payload")"
log_step "Downloading target release manifest"
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
log_step "Refreshing local runtime assets"
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

log_step "Pulling Docker image ${image}"
run_compose_update_step pull
log_step "Restarting Nagient container"
run_compose_update_step up -d

echo "Nagient upgraded: ${current_version} -> ${target_version}"
echo "Quick start: ${NAGIENT_HOME}/bin/nagient status"
