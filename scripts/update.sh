#!/usr/bin/env bash
set -euo pipefail

DEFAULT_CHANNEL="__NAGIENT_DEFAULT_CHANNEL__"
DEFAULT_UPDATE_BASE_URL="__NAGIENT_UPDATE_BASE_URL__"
UNRENDERED_UPDATE_BASE_URL_TOKEN="__NAGIENT_""UPDATE_BASE_URL__"

NAGIENT_CHANNEL="${NAGIENT_CHANNEL:-$DEFAULT_CHANNEL}"
NAGIENT_HOME="${NAGIENT_HOME:-$HOME/.nagient}"
NAGIENT_UPDATE_BASE_URL="${NAGIENT_UPDATE_BASE_URL:-${UPDATE_BASE_URL:-$DEFAULT_UPDATE_BASE_URL}}"
NAGIENT_WORKSPACE_DIR="${NAGIENT_WORKSPACE_DIR:-}"

refresh_paths() {
  NAGIENT_COMPOSE_FILE="${NAGIENT_HOME}/docker-compose.yml"
  NAGIENT_ENV_FILE="${NAGIENT_HOME}/.env"
  NAGIENT_BIN_DIR="${NAGIENT_HOME}/bin"
  NAGIENT_RELEASES_DIR="${NAGIENT_HOME}/releases"
  CURRENT_MANIFEST="${NAGIENT_RELEASES_DIR}/current.json"
  if [ -z "${NAGIENT_WORKSPACE_DIR:-}" ]; then
    NAGIENT_WORKSPACE_DIR="${NAGIENT_HOME}/workspace"
  fi
}

update_usage() {
  cat <<EOF
Usage: nagient-update [options]

Options:
  --home, --install-dir <path>  Use a custom Nagient installation directory
  --channel <name>              Override the release channel
  --update-base-url <url>       Override the update center base URL
  -h, --help                    Show this help
EOF
}

refresh_paths

while [ "$#" -gt 0 ]; do
  case "$1" in
    --home|--install-dir)
      NAGIENT_HOME="${2:-}"
      shift
      refresh_paths
      ;;
    --channel)
      NAGIENT_CHANNEL="${2:-}"
      shift
      ;;
    --update-base-url)
      NAGIENT_UPDATE_BASE_URL="${2:-}"
      shift
      ;;
    -h|--help)
      update_usage
      exit 0
      ;;
    *)
      echo "Unknown update option: $1" >&2
      update_usage >&2
      exit 1
      ;;
  esac
  shift
done

refresh_paths

mkdir -p "${NAGIENT_BIN_DIR}" "${NAGIENT_RELEASES_DIR}"

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
  if command -v python3.13 >/dev/null 2>&1; then
    echo "python3.13"
    return 0
  fi
  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
    return 0
  fi
  if command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  echo "python"
}

path_has_dir() {
  case ":${PATH:-}:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

detect_shell_link_dir() {
  local candidate=""
  local configured_dir="${NAGIENT_SHELL_LINK_DIR:-}"
  local original_ifs="$IFS"

  if [ -n "$configured_dir" ]; then
    printf '%s\n' "$configured_dir"
    return 0
  fi

  if path_has_dir "$NAGIENT_BIN_DIR"; then
    printf '%s\n' "$NAGIENT_BIN_DIR"
    return 0
  fi

  IFS=':'
  for candidate in ${PATH:-}; do
    [ -n "$candidate" ] || continue
    [ -d "$candidate" ] || continue
    [ -w "$candidate" ] || continue
    case "$candidate" in
      "$HOME"/*|/opt/homebrew/bin|/usr/local/bin)
        IFS="$original_ifs"
        printf '%s\n' "$candidate"
        return 0
        ;;
    esac
  done
  IFS="$original_ifs"

  printf '%s\n' "$HOME/.local/bin"
}

SHELL_LINK_DIR=""
SHELL_SHIMS_IN_PATH="false"

install_shell_shims() {
  SHELL_LINK_DIR="$(detect_shell_link_dir)"
  if ! mkdir -p "$SHELL_LINK_DIR"; then
    return 1
  fi

  if [ "$SHELL_LINK_DIR" != "$NAGIENT_BIN_DIR" ]; then
    ln -sf "${NAGIENT_BIN_DIR}/nagient" "${SHELL_LINK_DIR}/nagient" || return 1
    ln -sf "${NAGIENT_BIN_DIR}/nagientctl" "${SHELL_LINK_DIR}/nagientctl" || return 1
  fi

  if path_has_dir "$SHELL_LINK_DIR"; then
    SHELL_SHIMS_IN_PATH="true"
  else
    SHELL_SHIMS_IN_PATH="false"
  fi
}

fetch_url() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url"
    return 0
  fi
  wget -qO- "$url"
}

sync_codex_mountpoint() {
  local host_codex_dir="$HOME/.codex"
  local target_path="${NAGIENT_HOME}/.codex-host"

  if [ -d "$host_codex_dir" ]; then
    if [ -L "$target_path" ] || [ ! -e "$target_path" ]; then
      ln -sfn "$host_codex_dir" "$target_path"
      return 0
    fi
    if [ -d "$target_path" ] && [ -z "$(ls -A "$target_path" 2>/dev/null)" ]; then
      rmdir "$target_path" 2>/dev/null || true
      ln -sfn "$host_codex_dir" "$target_path"
      return 0
    fi
    return 0
  fi

  mkdir -p "$target_path"
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
  init               Show local Nagient files and first-run hints
  setup              Guided first-run provider setup
  status|st          Show compact runtime status
  doctor|cfg         Show detailed runtime diagnostics
  paths|config       Show local config and workspace paths
  shell-install      Install nagient/nagientctl shims into a PATH directory
  shellenv           Print PATH export for Nagient commands
  provider ...       Configure provider profiles without editing TOML manually
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

python_cmd() {
  if command -v python3.13 >/dev/null 2>&1; then
    echo "python3.13"
    return 0
  fi
  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
    return 0
  fi
  if command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  echo "Python 3 is required for Nagient setup commands." >&2
  exit 1
}

path_has_dir() {
  case ":${PATH:-}:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

detect_shell_link_dir() {
  local candidate=""
  local original_ifs="$IFS"

  if path_has_dir "${NAGIENT_HOME}/bin"; then
    printf '%s\n' "${NAGIENT_HOME}/bin"
    return 0
  fi

  IFS=':'
  for candidate in ${PATH:-}; do
    [ -n "$candidate" ] || continue
    [ -d "$candidate" ] || continue
    [ -w "$candidate" ] || continue
    case "$candidate" in
      "$HOME"/bin|"$HOME"/.local/bin|/opt/homebrew/bin|/usr/local/bin)
        IFS="$original_ifs"
        printf '%s\n' "$candidate"
        return 0
        ;;
    esac
  done
  IFS="$original_ifs"

  printf '%s\n' "$HOME/.local/bin"
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

shell_install() {
  local link_dir=""

  link_dir="$(detect_shell_link_dir)"
  mkdir -p "$link_dir"

  if [ "$link_dir" = "${NAGIENT_HOME}/bin" ]; then
    echo "Nagient commands already live in ${link_dir}"
  else
    ln -sf "${NAGIENT_HOME}/bin/nagient" "${link_dir}/nagient"
    ln -sf "${NAGIENT_HOME}/bin/nagientctl" "${link_dir}/nagientctl"
    echo "Installed Nagient commands into ${link_dir}"
  fi

  if path_has_dir "$link_dir"; then
    echo "Commands available: nagient, nagientctl"
  else
    echo "Add to PATH: export PATH=\"${link_dir}:\$PATH\""
  fi
}

print_shellenv() {
  local link_dir=""

  link_dir="$(detect_shell_link_dir)"
  echo "export PATH=\"${link_dir}:\$PATH\""
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

open_url() {
  local url="$1"
  if command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
    return 0
  fi
  return 1
}

resolve_codex_auth_file_default() {
  if [ -n "${NAGIENT_OPENAI_CODEX_AUTH_FILE:-}" ]; then
    printf '%s\n' "${NAGIENT_OPENAI_CODEX_AUTH_FILE}"
    return 0
  fi
  if [ -n "${CODEX_HOME:-}" ]; then
    printf '%s\n' "${CODEX_HOME%/}/auth.json"
    return 0
  fi
  printf '%s\n' "$HOME/.codex/auth.json"
}

container_codex_auth_file_default() {
  printf '%s\n' "/root/.codex/auth.json"
}

provider_usage() {
  cat <<USAGE
Usage: ${PROGRAM_NAME} provider <command>

Provider commands:
  list                        Show provider auth status
  enable <id> [options]       Enable/configure a provider profile
  use <id> [options]          Enable and make a provider the default
  disable <id>                Disable a provider profile
  models <id>                 Pass through to in-container model listing

Options for enable/use:
  --default                   Make this provider the default profile
  --model <name>              Override the configured model
  --api-key <value>           Store an API key in secrets.env
  --token <value>             Store a token credential via nagient auth login
  --base-url <url>            Override base_url
  --auth <mode>               Override auth mode
  --auth-file <path>          Override auth_file (used by openai-codex)
  --secret-name <name>        Override api_key_secret
  --plugin <plugin_id>        Use a custom provider plugin id
  --no-reconcile              Skip reconcile after editing files
USAGE
}

provider_defaults() {
  case "$1" in
    openai) printf '%s\n' 'builtin.openai|api_key|OPENAI_API_KEY|gpt-4.1-mini||' ;;
    openai-codex|openai_codex) printf '%s\n' 'builtin.openai_codex|oauth_browser|CODEX_API_KEY|gpt-5-codex||http://127.0.0.1:1455/auth/callback' ;;
    anthropic) printf '%s\n' 'builtin.anthropic|api_key|ANTHROPIC_API_KEY|claude-sonnet-4-5||' ;;
    gemini) printf '%s\n' 'builtin.gemini|api_key|GEMINI_API_KEY|gemini-2.5-pro||' ;;
    deepseek) printf '%s\n' 'builtin.deepseek|api_key|DEEPSEEK_API_KEY|deepseek-chat||' ;;
    ollama) printf '%s\n' 'builtin.ollama|none||llama3.1:8b|http://127.0.0.1:11434|' ;;
    *) return 1 ;;
  esac
}

upsert_env_secret() {
  local secrets_file="$1"
  local key="$2"
  local value="$3"

  "$(python_cmd)" - "$secrets_file" "$key" "$value" <<'PY'
import sys
from pathlib import Path

secrets_file = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

def serialize_env_value(raw: str) -> str:
    if not raw or any(char.isspace() for char in raw) or "#" in raw:
        escaped = raw.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return raw

secrets_file.parent.mkdir(parents=True, exist_ok=True)
lines = secrets_file.read_text(encoding="utf-8").splitlines() if secrets_file.exists() else []
serialized = f"{key}={serialize_env_value(value)}"
updated = False

for index, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith("export "):
        stripped = stripped[7:].strip()
    if not stripped or "=" not in stripped:
        continue
    candidate_key = stripped.split("=", 1)[0].strip()
    if candidate_key == key:
        lines[index] = serialized
        updated = True
        break

if not updated:
    lines.append(serialized)

secrets_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY
}

update_provider_config() {
  local provider_id="$1"
  local enabled="$2"
  local default_flag="$3"
  local model="$4"
  local auth_mode="$5"
  local secret_name="$6"
  local base_url="$7"
  local auth_file="$8"
  local plugin_id="$9"

  "$(python_cmd)" - \
    "$NAGIENT_CONFIG_FILE" \
    "$provider_id" \
    "$enabled" \
    "$default_flag" \
    "$model" \
    "$auth_mode" \
    "$secret_name" \
    "$base_url" \
    "$auth_file" \
    "$plugin_id" <<'PY'
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

config_file = Path(sys.argv[1])
provider_id = sys.argv[2]
enabled = sys.argv[3] == "true"
default_flag = sys.argv[4] == "true"
model = sys.argv[5]
auth_mode = sys.argv[6]
secret_name = sys.argv[7]
base_url = sys.argv[8]
auth_file = sys.argv[9]
plugin_id = sys.argv[10]


def ensure_mapping(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    created: dict[str, object] = {}
    payload[key] = created
    return created


def render_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(render_toml_value(item) for item in value) + "]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_table(lines: list[str], payload: dict[str, object], prefix: list[str]) -> None:
    scalar_items = [
        (key, value) for key, value in payload.items() if not isinstance(value, dict)
    ]
    nested_items = [
        (key, value) for key, value in payload.items() if isinstance(value, dict)
    ]
    if prefix:
        lines.append(f"[{'.'.join(prefix)}]")
    for key, value in scalar_items:
        lines.append(f"{key} = {render_toml_value(value)}")
    if scalar_items and nested_items:
        lines.append("")
    for index, (key, value) in enumerate(nested_items):
        render_table(lines, value, [*prefix, key])
        if index != len(nested_items) - 1:
            lines.append("")


def render_toml(payload: dict[str, object]) -> str:
    lines: list[str] = []
    render_table(lines, payload, [])
    return "\n".join(lines).rstrip() + "\n"


payload: dict[str, object] = {}
if config_file.exists():
    loaded = tomllib.loads(config_file.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        payload = dict(loaded)

providers = ensure_mapping(payload, "providers")
profile = providers.get(provider_id)
if not isinstance(profile, dict):
    profile = {}

if plugin_id:
    profile["plugin"] = plugin_id
elif "plugin" not in profile:
    profile["plugin"] = f"builtin.{provider_id}"

profile["enabled"] = enabled
if auth_mode:
    profile["auth"] = auth_mode
if model:
    profile["model"] = model
if secret_name:
    profile["api_key_secret"] = secret_name
if base_url:
    profile["base_url"] = base_url
if auth_file:
    if auth_mode == "oauth_browser" and auth_file.startswith(("http://", "https://")):
        profile["redirect_uri"] = auth_file
    else:
        profile["auth_file"] = auth_file

providers[provider_id] = profile

agent = ensure_mapping(payload, "agent")
if default_flag:
    agent["default_provider"] = provider_id
    agent["require_provider"] = True
elif not enabled and str(agent.get("default_provider", "")).strip() == provider_id:
    agent["default_provider"] = ""
    agent["require_provider"] = False

config_file.parent.mkdir(parents=True, exist_ok=True)
config_file.write_text(render_toml(payload), encoding="utf-8")
PY
}

init_runtime() {
  echo "Nagient files are ready in ${NAGIENT_HOME}"
  print_paths
  echo "Next: ${PROGRAM_NAME} setup"
}

list_providers() {
  require_compose_files
  compose_exec nagient auth status --format text
}

complete_openai_codex_browser_login() {
  local provider_id="$1"
  local login_payload=""
  local session_id=""
  local authorization_url=""
  local callback_input=""

  require_compose_files
  login_payload="$(compose_exec nagient auth login "$provider_id" --format json)"
  session_id="$("$(python_cmd)" - <<'PY' "$login_payload"
import json
import sys
payload = json.loads(sys.argv[1])
print(payload.get("session", {}).get("session_id", ""))
PY
)"
  authorization_url="$("$(python_cmd)" - <<'PY' "$login_payload"
import json
import sys
payload = json.loads(sys.argv[1])
print(payload.get("session", {}).get("authorization_url", ""))
PY
)"

  if [ -z "$session_id" ] || [ -z "$authorization_url" ]; then
    echo "Could not start OpenAI Codex browser login." >&2
    echo "$login_payload" >&2
    return 1
  fi

  echo "OpenAI Codex login URL:"
  echo "$authorization_url"
  if [ -t 0 ]; then
    printf 'Open browser now? [Y/n]: '
    read -r callback_input
    case "${callback_input:-Y}" in
      n|N|no|NO)
        ;;
      *)
        open_url "$authorization_url" || true
        ;;
    esac

    echo "After login, paste the full redirect URL from the browser."
    echo "If you only have the code, paste just the code."
    printf 'Callback URL or code: '
    read -r callback_input
  fi

  if [ -z "${callback_input:-}" ]; then
    echo "Login session created. Complete it later with:"
    echo "  nagient auth complete $provider_id --session-id $session_id --callback-url '<redirect-url>'"
    return 0
  fi

  case "$callback_input" in
    http://*|https://*)
      compose_exec nagient auth complete "$provider_id" --session-id "$session_id" --callback-url "$callback_input" --format text
      ;;
    *)
      compose_exec nagient auth complete "$provider_id" --session-id "$session_id" --code "$callback_input" --format text
      ;;
  esac
}

provider_enable() {
  local provider_id="${1:-}"
  local default_flag="false"
  local model=""
  local api_key=""
  local token=""
  local base_url=""
  local auth_mode=""
  local auth_file=""
  local secret_name=""
  local plugin_id=""
  local no_reconcile="false"
  local defaults=""
  local default_plugin=""
  local default_auth=""
  local default_secret=""
  local default_model=""
  local default_base_url=""
  local default_auth_file=""

  if [ -z "$provider_id" ]; then
    echo "Usage: ${PROGRAM_NAME} provider enable <provider_id>" >&2
    return 1
  fi
  shift || true

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --default)
        default_flag="true"
        ;;
      --model)
        model="${2:-}"
        shift
        ;;
      --api-key)
        api_key="${2:-}"
        shift
        ;;
      --token)
        token="${2:-}"
        shift
        ;;
      --base-url)
        base_url="${2:-}"
        shift
        ;;
      --auth)
        auth_mode="${2:-}"
        shift
        ;;
      --auth-file)
        auth_file="${2:-}"
        shift
        ;;
      --secret-name)
        secret_name="${2:-}"
        shift
        ;;
      --plugin)
        plugin_id="${2:-}"
        shift
        ;;
      --no-reconcile)
        no_reconcile="true"
        ;;
      *)
        echo "Unknown provider option: $1" >&2
        return 1
        ;;
    esac
    shift
  done

  if defaults="$(provider_defaults "$provider_id" 2>/dev/null)"; then
    IFS='|' read -r default_plugin default_auth default_secret default_model default_base_url default_auth_file <<EOF
$defaults
EOF
  elif [ -z "$plugin_id" ]; then
    echo "Unknown built-in provider: $provider_id" >&2
    echo "Supported built-ins: openai, openai-codex, anthropic, gemini, deepseek, ollama" >&2
    echo "Use --plugin for a custom provider profile." >&2
    return 1
  fi

  [ -n "$plugin_id" ] || plugin_id="$default_plugin"
  [ -n "$auth_mode" ] || auth_mode="$default_auth"
  [ -n "$secret_name" ] || secret_name="$default_secret"
  [ -n "$model" ] || model="$default_model"
  [ -n "$base_url" ] || base_url="$default_base_url"
  [ -n "$auth_file" ] || auth_file="$default_auth_file"

  update_provider_config \
    "$provider_id" \
    "true" \
    "$default_flag" \
    "$model" \
    "$auth_mode" \
    "$secret_name" \
    "$base_url" \
    "$auth_file" \
    "$plugin_id"

  if [ -n "$api_key" ]; then
    if [ -z "$secret_name" ]; then
      echo "This provider needs --secret-name before storing an API key." >&2
      return 1
    fi
    upsert_env_secret "$NAGIENT_SECRETS_FILE" "$secret_name" "$api_key"
  fi

  if [ -n "$token" ]; then
    require_compose_files
    compose_exec nagient auth login "$provider_id" --token "$token" --format json >/dev/null
  fi

  echo "Configured provider '${provider_id}'."
  echo "Config: ${NAGIENT_CONFIG_FILE}"
  if [ -n "$api_key" ]; then
    echo "Secret stored in: ${NAGIENT_SECRETS_FILE}"
  fi

  if [ "$no_reconcile" = "true" ]; then
    echo "Run \`${PROGRAM_NAME} reconcile\` when ready."
    return 0
  fi

  if [ "$auth_mode" = "oauth_browser" ] && [ -z "$token" ] && [ -z "$api_key" ]; then
    echo "Run \`${PROGRAM_NAME} auth login ${provider_id}\` to finish browser authentication."
    return 0
  fi

  if [ ! -f "$NAGIENT_COMPOSE_FILE" ] || [ ! -f "$NAGIENT_ENV_FILE" ]; then
    echo "Run \`${PROGRAM_NAME} reconcile\` after the runtime is installed."
    return 0
  fi

  require_compose_files
  compose_exec nagient reconcile --format text
}

provider_disable() {
  local provider_id="${1:-}"
  local no_reconcile="false"

  if [ -z "$provider_id" ]; then
    echo "Usage: ${PROGRAM_NAME} provider disable <provider_id>" >&2
    return 1
  fi
  shift || true

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --no-reconcile)
        no_reconcile="true"
        ;;
      *)
        echo "Unknown provider option: $1" >&2
        return 1
        ;;
    esac
    shift
  done

  update_provider_config "$provider_id" "false" "false" "" "" "" "" "" ""
  echo "Disabled provider '${provider_id}'."
  echo "Config: ${NAGIENT_CONFIG_FILE}"

  if [ "$no_reconcile" = "true" ]; then
    echo "Run \`${PROGRAM_NAME} reconcile\` when ready."
    return 0
  fi

  if [ ! -f "$NAGIENT_COMPOSE_FILE" ] || [ ! -f "$NAGIENT_ENV_FILE" ]; then
    echo "Run \`${PROGRAM_NAME} reconcile\` after the runtime is installed."
    return 0
  fi

  require_compose_files
  compose_exec nagient reconcile --format text
}

provider_use() {
  local provider_id="${1:-}"

  if [ -n "$provider_id" ]; then
    shift
  fi

  provider_enable "$provider_id" --default "$@"
}

setup_runtime() {
  local provider_id=""
  local model=""
  local api_key=""
  local token=""
  local base_url=""
  local auth_mode=""
  local auth_file=""
  local secret_name=""
  local plugin_id=""
  local no_reconcile="false"
  local defaults=""
  local default_plugin=""
  local default_auth=""
  local default_secret=""
  local default_model=""
  local default_base_url=""
  local default_auth_file=""
  local answer=""
  local provider_args=()

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --provider)
        provider_id="${2:-}"
        shift
        ;;
      --model)
        model="${2:-}"
        shift
        ;;
      --api-key)
        api_key="${2:-}"
        shift
        ;;
      --token)
        token="${2:-}"
        shift
        ;;
      --base-url)
        base_url="${2:-}"
        shift
        ;;
      --auth)
        auth_mode="${2:-}"
        shift
        ;;
      --auth-file)
        auth_file="${2:-}"
        shift
        ;;
      --secret-name)
        secret_name="${2:-}"
        shift
        ;;
      --plugin)
        plugin_id="${2:-}"
        shift
        ;;
      --no-reconcile)
        no_reconcile="true"
        ;;
      *)
        echo "Unknown setup option: $1" >&2
        return 1
        ;;
    esac
    shift
  done

  if [ -z "$provider_id" ]; then
    if [ ! -t 0 ]; then
      echo "Use \`${PROGRAM_NAME} setup --provider <id>\` in non-interactive shells." >&2
      return 1
    fi

    echo "Choose a provider profile:"
    PS3="Provider [1-6]: "
    select provider_id in openai openai-codex anthropic gemini deepseek ollama; do
      [ -n "$provider_id" ] && break
    done
  fi

  if defaults="$(provider_defaults "$provider_id" 2>/dev/null)"; then
    IFS='|' read -r default_plugin default_auth default_secret default_model default_base_url default_auth_file <<EOF
$defaults
EOF
  elif [ -z "$plugin_id" ]; then
    echo "Unknown built-in provider: $provider_id" >&2
    echo "Use \`${PROGRAM_NAME} setup --provider <id> --plugin <plugin_id>\` for custom providers." >&2
    return 1
  fi

  [ -n "$plugin_id" ] || plugin_id="$default_plugin"
  [ -n "$auth_mode" ] || auth_mode="$default_auth"
  [ -n "$secret_name" ] || secret_name="$default_secret"
  [ -n "$auth_file" ] || auth_file="$default_auth_file"

  if [ "$provider_id" = "openai-codex" ] && [ -t 0 ] && [ -z "$api_key" ] && [ -z "$token" ]; then
    echo "Choose OpenAI Codex authentication:"
    echo "  1) Browser login"
    echo "  2) Import existing ~/.codex session"
    echo "  3) API key"
    printf 'Auth mode [1-3, default 1]: '
    read -r answer
    case "${answer:-1}" in
      2)
        auth_mode="codex_auth_file"
        auth_file="$(container_codex_auth_file_default)"
        ;;
      3)
        auth_mode="api_key"
        auth_file=""
        ;;
      *)
        auth_mode="oauth_browser"
        auth_file="${default_auth_file}"
        ;;
    esac
  fi

  if [ -z "$model" ] && [ -t 0 ] && [ -n "$default_model" ]; then
    printf 'Model [%s]: ' "$default_model"
    read -r answer
    model="${answer:-$default_model}"
  fi
  [ -n "$model" ] || model="$default_model"

  if [ -z "$base_url" ] && [ -t 0 ] && [ -n "$default_base_url" ]; then
    printf 'Base URL [%s]: ' "$default_base_url"
    read -r answer
    base_url="${answer:-$default_base_url}"
  fi
  [ -n "$base_url" ] || base_url="$default_base_url"

  if [ "$provider_id" = "openai-codex" ] && [ "$auth_mode" = "codex_auth_file" ] && [ -t 0 ]; then
    local host_codex_auth=""
    host_codex_auth="$(resolve_codex_auth_file_default)"
    echo "Nagient will reuse the host Codex session from:"
    echo "  ${host_codex_auth}"
    if [ ! -f "$host_codex_auth" ]; then
      echo "No host Codex auth file exists yet."
      echo "You can switch to browser login or API key, or sign in with Codex first."
      return 1
    fi
    auth_file="$(container_codex_auth_file_default)"
  fi

  if [ "$auth_mode" = "api_key" ] && [ -z "$api_key" ] && [ -t 0 ]; then
    printf 'API key for %s (leave empty to add later): ' "$provider_id" >&2
    read -rs api_key
    printf '\n' >&2
  fi

  provider_args=(--default)
  if [ -n "$model" ]; then
    provider_args+=(--model "$model")
  fi
  if [ -n "$api_key" ]; then
    provider_args+=(--api-key "$api_key")
  fi
  if [ -n "$token" ]; then
    provider_args+=(--token "$token")
  fi
  if [ -n "$base_url" ]; then
    provider_args+=(--base-url "$base_url")
  fi
  if [ -n "$auth_mode" ]; then
    provider_args+=(--auth "$auth_mode")
  fi
  if [ -n "$auth_file" ]; then
    provider_args+=(--auth-file "$auth_file")
  fi
  if [ -n "$secret_name" ]; then
    provider_args+=(--secret-name "$secret_name")
  fi
  if [ -n "$plugin_id" ]; then
    provider_args+=(--plugin "$plugin_id")
  fi
  if [ "$no_reconcile" = "true" ]; then
    provider_args+=(--no-reconcile)
  fi

  provider_enable "$provider_id" "${provider_args[@]}"

  if [ "$provider_id" = "openai-codex" ] && [ "$auth_mode" = "oauth_browser" ] && [ -z "$api_key" ] && [ -z "$token" ]; then
    complete_openai_codex_browser_login "$provider_id" || return 1
    require_compose_files
    compose_exec nagient reconcile --format text
  fi
}

command_name="${1:-help}"
if [ "$#" -gt 0 ]; then
  shift
fi

case "$command_name" in
  init)
    init_runtime
    ;;
  setup)
    setup_runtime "$@"
    ;;
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
  shell-install|link)
    shell_install
    ;;
  shellenv)
    print_shellenv
    ;;
  provider)
    subcommand="${1:-list}"
    if [ "$#" -gt 0 ]; then
      shift
    fi
    case "$subcommand" in
      list|ls|status)
        list_providers
        ;;
      enable)
        provider_enable "$@"
        ;;
      use|default)
        provider_use "$@"
        ;;
      disable)
        provider_disable "$@"
        ;;
      models)
        require_compose_files
        compose_exec nagient provider models "$@"
        ;;
      help|-h|--help)
        provider_usage
        ;;
      *)
        require_compose_files
        compose_exec nagient provider "$subcommand" "$@"
        ;;
    esac
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
sync_codex_mountpoint
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
