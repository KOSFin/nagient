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
NAGIENT_CONFIG_FILE="${NAGIENT_HOME}/config.toml"
NAGIENT_SECRETS_FILE="${NAGIENT_HOME}/secrets.env"
NAGIENT_TOOL_SECRETS_FILE="${NAGIENT_HOME}/tool-secrets.env"
NAGIENT_PLUGINS_DIR="${NAGIENT_HOME}/plugins"
NAGIENT_TOOLS_DIR="${NAGIENT_HOME}/tools"
NAGIENT_PROVIDERS_DIR="${NAGIENT_HOME}/providers"
NAGIENT_CREDENTIALS_DIR="${NAGIENT_HOME}/credentials"
NAGIENT_STATE_DIR="${NAGIENT_HOME}/state"
NAGIENT_LOG_DIR="${NAGIENT_HOME}/logs"
NAGIENT_RELEASES_DIR="${NAGIENT_HOME}/releases"
NAGIENT_BIN_DIR="${NAGIENT_HOME}/bin"
NAGIENT_WORKSPACE_DIR="${NAGIENT_HOME}/workspace"

update_base_url_is_unrendered() {
  case "$1" in
    *"$UNRENDERED_UPDATE_BASE_URL_TOKEN"*) return 0 ;;
    *) return 1 ;;
  esac
}

ensure_release_defaults() {
  if [ -z "$NAGIENT_UPDATE_BASE_URL" ] || {
    update_base_url_is_unrendered "$DEFAULT_UPDATE_BASE_URL" &&
    update_base_url_is_unrendered "$NAGIENT_UPDATE_BASE_URL"
  }; then
    echo "NAGIENT_UPDATE_BASE_URL is not configured." >&2
    echo "Use a rendered installer asset or export NAGIENT_UPDATE_BASE_URL/UPDATE_BASE_URL explicitly." >&2
    exit 1
  fi

  if [ "$NAGIENT_CHANNEL" = "__NAGIENT_DEFAULT_CHANNEL__" ]; then
    NAGIENT_CHANNEL="stable"
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

log_step() {
  printf '[nagient] %s\n' "$1"
}

require_docker_runtime() {
  local compose_error=""
  local docker_error=""

  if ! compose_error="$(docker compose version 2>&1 >/dev/null)"; then
    echo "Docker Compose v2 is required." >&2
    echo "Install Docker Desktop or Docker Engine with the Compose plugin, then retry." >&2
    if [ -n "$compose_error" ]; then
      echo "$compose_error" >&2
    fi
    exit 1
  fi

  if ! docker_error="$(docker info 2>&1 >/dev/null)"; then
    echo "Docker is installed but the daemon is not available." >&2
    echo "Start Docker Desktop (macOS/Windows) or the Docker service (Linux), then retry." >&2
    echo "If you use a custom Docker context or socket, make sure 'docker info' succeeds first." >&2
    if [ -n "$docker_error" ]; then
      echo "$docker_error" >&2
    fi
    exit 1
  fi
}

run_compose_install_step() {
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
        echo "DOCKER_DEFAULT_PLATFORM=linux/amd64 curl -fsSL https://ngnt-in.ruka.me/install.sh | bash" >&2
        ;;
    esac
    exit 1
  fi
  rm -f "$log_file"
}

python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  echo "Python 3 is required for manifest parsing." >&2
  exit 1
}

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

download_artifact() {
  local url="$1"
  local target="$2"
  mkdir -p "$(dirname "$target")"
  fetch_url "$url" >"$target"
  chmod +x "$target" || true
}

write_nagientctl() {
  cat >"${NAGIENT_BIN_DIR}/nagientctl" <<'NAGIENTCTL'
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
  chmod +x "${NAGIENT_BIN_DIR}/nagientctl"
  cp "${NAGIENT_BIN_DIR}/nagientctl" "${NAGIENT_BIN_DIR}/nagient"
  chmod +x "${NAGIENT_BIN_DIR}/nagient"
}

require_cmd docker
require_docker_runtime
ensure_release_defaults
mkdir -p "$NAGIENT_HOME" "$NAGIENT_RELEASES_DIR" "$NAGIENT_BIN_DIR" "$NAGIENT_PLUGINS_DIR" "$NAGIENT_TOOLS_DIR" "$NAGIENT_PROVIDERS_DIR" "$NAGIENT_CREDENTIALS_DIR" "$NAGIENT_STATE_DIR" "$NAGIENT_LOG_DIR" "$NAGIENT_WORKSPACE_DIR"

channel_payload="$(mktemp)"
manifest_payload="$(mktemp)"
trap 'rm -f "$channel_payload" "$manifest_payload"' EXIT

log_step "Resolving release channel metadata"
fetch_url "${NAGIENT_UPDATE_BASE_URL%/}/channels/${NAGIENT_CHANNEL}.json" >"$channel_payload"
manifest_url="$(json_field manifest_url "$channel_payload")"
log_step "Downloading release manifest"
fetch_url "$manifest_url" >"$manifest_payload"

compose_url="$(json_field docker.compose_url "$manifest_payload")"
image="$(json_field docker.image "$manifest_payload")"
version="$(json_field version "$manifest_payload")"
update_url="$(artifact_url update.sh "$manifest_payload")"
uninstall_url="$(artifact_url uninstall.sh "$manifest_payload")"

log_step "Writing runtime assets into ${NAGIENT_HOME}"
download_artifact "$compose_url" "$NAGIENT_COMPOSE_FILE"
download_artifact "$update_url" "${NAGIENT_BIN_DIR}/nagient-update"
download_artifact "$uninstall_url" "${NAGIENT_BIN_DIR}/nagient-uninstall"
write_nagientctl
cp "$manifest_payload" "${NAGIENT_RELEASES_DIR}/current.json"
cp "$manifest_payload" "${NAGIENT_RELEASES_DIR}/${version}.json"

if [ ! -f "$NAGIENT_CONFIG_FILE" ]; then
  cat >"$NAGIENT_CONFIG_FILE" <<EOF
[updates]
channel = "${NAGIENT_CHANNEL}"
base_url = "${NAGIENT_UPDATE_BASE_URL}"

[runtime]
heartbeat_interval_seconds = 30
safe_mode = true

[docker]
project_name = "nagient"

[paths]
secrets_file = "${NAGIENT_SECRETS_FILE}"
tool_secrets_file = "${NAGIENT_TOOL_SECRETS_FILE}"
plugins_dir = "${NAGIENT_PLUGINS_DIR}"
tools_dir = "${NAGIENT_TOOLS_DIR}"
providers_dir = "${NAGIENT_PROVIDERS_DIR}"
credentials_dir = "${NAGIENT_CREDENTIALS_DIR}"

[agent]
default_provider = ""
require_provider = false

[transports.console]
plugin = "builtin.console"
enabled = true

[transports.webhook]
plugin = "builtin.webhook"
enabled = false
listen_host = "0.0.0.0"
listen_port = 8080
path = "/events"
shared_secret_name = "NAGIENT_WEBHOOK_SHARED_SECRET"

[transports.telegram]
plugin = "builtin.telegram"
enabled = false
bot_token_secret = "TELEGRAM_BOT_TOKEN"
default_chat_id = ""

[providers.openai]
plugin = "builtin.openai"
enabled = false
auth = "api_key"
api_key_secret = "OPENAI_API_KEY"
model = "gpt-4.1-mini"

[providers.anthropic]
plugin = "builtin.anthropic"
enabled = false
auth = "api_key"
api_key_secret = "ANTHROPIC_API_KEY"
model = "claude-sonnet-4-5"

[providers.gemini]
plugin = "builtin.gemini"
enabled = false
auth = "api_key"
api_key_secret = "GEMINI_API_KEY"
model = "gemini-2.5-pro"

[providers.deepseek]
plugin = "builtin.deepseek"
enabled = false
auth = "api_key"
api_key_secret = "DEEPSEEK_API_KEY"
model = "deepseek-chat"

[providers.ollama]
plugin = "builtin.ollama"
enabled = false
auth = "none"
base_url = "http://127.0.0.1:11434"
model = "llama3.1:8b"
EOF
fi

if [ ! -f "$NAGIENT_SECRETS_FILE" ]; then
  cat >"$NAGIENT_SECRETS_FILE" <<EOF
# Fill only the secrets you actually use.
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# GEMINI_API_KEY=
# DEEPSEEK_API_KEY=
# TELEGRAM_BOT_TOKEN=
# NAGIENT_WEBHOOK_SHARED_SECRET=
EOF
fi

if [ ! -f "$NAGIENT_TOOL_SECRETS_FILE" ]; then
  cat >"$NAGIENT_TOOL_SECRETS_FILE" <<'EOF'
# Add tool-scoped secrets here when needed.
EOF
fi

cat >"$NAGIENT_ENV_FILE" <<EOF
NAGIENT_IMAGE=${image}
NAGIENT_CHANNEL=${NAGIENT_CHANNEL}
NAGIENT_UPDATE_BASE_URL=${NAGIENT_UPDATE_BASE_URL}
NAGIENT_CONTAINER_NAME=nagient
NAGIENT_DOCKER_PROJECT_NAME=nagient
NAGIENT_SAFE_MODE=true
EOF

log_step "Pulling Docker image ${image}"
run_compose_install_step pull
log_step "Starting Nagient container"
run_compose_install_step up -d

echo "Nagient ${version} installed into ${NAGIENT_HOME}"
echo "Quick start: ${NAGIENT_BIN_DIR}/nagient status"
echo "Config paths: ${NAGIENT_BIN_DIR}/nagient paths"
echo "Updater: ${NAGIENT_BIN_DIR}/nagient update"
echo "Optional PATH: export PATH=\"${NAGIENT_BIN_DIR}:\$PATH\""
