# Environment Variables

Language: English | [Русский](env.ru.md)

## 1. Installer variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `NAGIENT_HOME` | Runtime root | `~/.nagient` |
| `NAGIENT_CHANNEL` | Update channel | `stable` |
| `NAGIENT_UPDATE_BASE_URL` | Update center URL | Embedded in release installer |

The installer also accepts `UPDATE_BASE_URL` as a compatibility override when you run a rendered script manually.

## 2. Docker Compose `.env` variables

File: `~/.nagient/.env`

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

## 3. Runtime variables (used by the app)

### 3.1 Paths

- `NAGIENT_HOME`
- `NAGIENT_CONFIG`
- `NAGIENT_SECRETS_FILE`
- `NAGIENT_TOOL_SECRETS_FILE`
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

## 4. Dynamic overrides

Provider override:

```env
NAGIENT_PROVIDER__OPENAI__ENABLED=true
NAGIENT_PROVIDER__OPENAI__MODEL=gpt-4.1-mini
```

Tool override:

```env
NAGIENT_TOOL__GITHUB_API__ENABLED=true
NAGIENT_TOOL__GITHUB_API__TOKEN_SECRET=GITHUB_TOKEN
```
