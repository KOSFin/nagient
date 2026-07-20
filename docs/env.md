# Environment Variables

Language: English | [Русский](env.ru.md)

## 1. Installer variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `NAGIENT_HOME` | Runtime root | `~/.nagient` |
| `NAGIENT_CHANNEL` | Update channel | `stable` |
| `NAGIENT_UPDATE_BASE_URL` | Update center URL | Embedded in release installer |

The installer also accepts `UPDATE_BASE_URL` as a compatibility override when you run a rendered script manually.

## 2. Docker Compose env-only deployment

The repository-root `docker-compose.yml` loads the complete `.env` file into the
container. For a custom path, set `NAGIENT_ENV_FILE` before `docker compose up`.

| Variable | Purpose | Example |
| --- | --- | --- |
| `NAGIENT_IMAGE` | Container image tag | `docker.io/parampo/nagient:0.1.0` |
| `NAGIENT_CHANNEL` | Update channel | `stable` |
| `NAGIENT_UPDATE_BASE_URL` | Base update center URL | `https://ngnt-in.ruka.me` |
| `NAGIENT_CONTAINER_NAME` | Container name | `nagient` |
| `NAGIENT_DOCKER_PROJECT_NAME` | Compose project name | `nagient` |
| `NAGIENT_SAFE_MODE` | Safe mode | `true` |
| `NAGIENT_WORKSPACE_ROOT` | Workspace root | `/workspace` |
| `NAGIENT_HEARTBEAT_INTERVAL` | Heartbeat interval (seconds) | `30` |
| `NAGIENT_WEBHOOK_BIND_ADDRESS` | Host interface for the webhook port | `127.0.0.1` |
| `NAGIENT_WEBHOOK_PORT` | Published host webhook port | `8080` |

## 3. Runtime variables (used by the app)

### 3.1 Paths

- `NAGIENT_HOME`
- `NAGIENT_CONFIG`
- `NAGIENT_SECRETS_FILE`
- `NAGIENT_TOOL_SECRETS_FILE`
- `NAGIENT_PROMPTS_DIR`
- `NAGIENT_PLUGINS_DIR`
- `NAGIENT_TOOLS_DIR`
- `NAGIENT_PROVIDERS_DIR`
- `NAGIENT_CREDENTIALS_DIR`
- `NAGIENT_STATE_DIR`
- `NAGIENT_LOG_DIR`
- `NAGIENT_RELEASES_DIR`

### 3.2 Runtime behavior

- `NAGIENT_CHANNEL`
- `NAGIENT_UPDATE_BASE_URL`
- `NAGIENT_HEARTBEAT_INTERVAL`
- `NAGIENT_DOCKER_PROJECT_NAME`
- `NAGIENT_SAFE_MODE`

### 3.3 Workspace and agent

- `NAGIENT_WORKSPACE_ROOT`
- `NAGIENT_WORKSPACE_MODE` (`bounded` or `unsafe`)
- `NAGIENT_AGENT_DEFAULT_PROVIDER`
- `NAGIENT_AGENT_REQUIRE_PROVIDER`
- `NAGIENT_AGENT__<FIELD>` for any direct `[agent]` field, for example
  `NAGIENT_AGENT__MAX_TURNS=20`
- `NAGIENT_AGENT_MEMORY__<FIELD>`
- `NAGIENT_AGENT_LOGGING__<FIELD>`
- `NAGIENT_AGENT_PROGRESS__<FIELD>`

## 4. Dynamic provider, transport, and tool overrides

Plugin-specific fields are documented by the plugin itself and can be inspected
with `nagient plugin catalog list --format json`. The same naming rule applies to
all extensions: `NAGIENT_<FAMILY>__<PLUGIN_ID>__<FIELD>`.

Provider override:

```env
NAGIENT_PROVIDER__OPENAI__ENABLED=true
NAGIENT_PROVIDER__OPENAI__MODEL=gpt-4.1-mini
```

Transport override:

```env
NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=builtin.telegram
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
NAGIENT_TRANSPORT__TELEGRAM__DEFAULT_CHAT_ID=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS=-1001234567890,123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=private,supergroup
```

Tool override:

```env
NAGIENT_TOOL__GITHUB_API__ENABLED=true
NAGIENT_TOOL__GITHUB_API__TOKEN_SECRET=GITHUB_TOKEN
NAGIENT_TOOL__GITHUB_API__BASE_URL=https://api.github.com
NAGIENT_TOOL__WORKSPACE_GIT__AUTHOR_NAME=Nagient Agent
NAGIENT_TOOL__WORKSPACE_GIT__AUTHOR_EMAIL=agent@example.com
NAGIENT_TOOL__WORKSPACE_GIT__USERNAME=git-user
NAGIENT_TOOL__WORKSPACE_GIT__TOKEN_SECRET=GIT_ACCESS_TOKEN
```

IDs and field names are case-insensitive in variable names. The runtime lowers
them before merging. A provider ID containing a hyphen can use an underscore,
for example `OPENAI_CODEX` maps to the existing `openai-codex` profile.

## 5. Secrets from the environment

When a provider, transport, or tool field refers to a secret name, a variable
with that name is read directly from the container environment:

```env
NAGIENT_PROVIDER__OPENAI__API_KEY_SECRET=OPENAI_API_KEY
OPENAI_API_KEY=sk-...
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN=123456:ABC...
```

For arbitrary or generated names, JSON objects are also supported:

```env
NAGIENT_SECRETS_JSON={"CUSTOM_PROVIDER_KEY":"value"}
NAGIENT_TOOL_SECRETS_JSON={"CUSTOM_TOOL_TOKEN":"value"}
```

## 6. Complete JSON configuration

`NAGIENT_CONFIG_JSON` accepts a JSON object with the same hierarchy as
`config.toml`. It is deep-merged, so it can express every existing nested field
and future plugin configuration without adding a new compose mapping:

```env
NAGIENT_CONFIG_JSON={"agent":{"max_turns":20,"progress":{"enabled":true}},"workspace":{"mode":"bounded"}}
```

Precedence, highest first:

1. granular environment variables;
2. `NAGIENT_CONFIG_JSON` and secret JSON variables;
3. persisted `config.toml`, `secrets.env`, and `tool-secrets.env`;
4. built-in defaults.
