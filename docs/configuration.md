# Configuration

Language: English | [Русский](configuration.ru.md)

## 1. Runtime location

Base path: `~/.nagient`

Layout:

```text
~/.nagient/
  config.toml
  secrets.env
  tool-secrets.env
  .env
  docker-compose.yml
  bin/
  prompts/
  plugins/
  tools/
  providers/
  credentials/
  state/
  logs/
  releases/
  workspace/
```

## 2. Minimal working flow

1. Install Nagient.
2. Run `nagient setup`.
3. Configure a provider, transport, workspace, and tool secrets from the setup menus.
4. Use `nagient paths` when you need the exact alias-expanded paths.
5. Run:

```bash
nagient preflight
nagient reconcile
nagient status
```

## 3. Path aliases

Config files and setup prompts accept these canonical aliases:

- `@home`, `@config`, `@secrets`, `@tool_secrets`, `@prompts`
- `@plugins`, `@tools`, `@providers`, `@credentials`
- `@state`, `@logs`, `@releases`

## 4. Example `config.toml`

```toml
[updates]
channel = "stable"
base_url = "https://ngnt-in.ruka.me"

[runtime]
heartbeat_interval_seconds = 30
safe_mode = true

[docker]
project_name = "nagient"

[paths]
secrets_file = "@secrets"
tool_secrets_file = "@tool_secrets"
prompts_dir = "@prompts"
plugins_dir = "@plugins"
tools_dir = "@tools"
providers_dir = "@providers"
credentials_dir = "@credentials"
state_dir = "@state"
log_dir = "@logs"
releases_dir = "@releases"

[workspace]
root = "@home/workspace"
mode = "bounded"

[agent]
default_provider = "openai"
require_provider = true
system_prompt_file = "@prompts/system.md"

[agent.progress]
enabled = false

[providers.openai]
plugin = "builtin.openai"
enabled = true
auth = "api_key"
api_key_secret = "OPENAI_API_KEY"
model = "gpt-4.1-mini"

[tools.workspace_fs]
plugin = "workspace.fs"
enabled = true

[tools.workspace_shell]
plugin = "workspace.shell"
enabled = true
timeout_seconds = 15
max_output_chars = 8000
default_ping_count = 4
normalize_infinite_commands = true
enforce_finite_commands = true

[tools.workspace_git]
plugin = "workspace.git"
enabled = true
author_name = "Nagient Agent"
author_email = "agent@example.com"
username = "git-user"
token_secret = "GIT_ACCESS_TOKEN"

[tools.system_config]
plugin = "system.config"
enabled = true
```

## 5. Secrets

`secrets.env`:

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
DEEPSEEK_API_KEY=
TELEGRAM_BOT_TOKEN=
NAGIENT_WEBHOOK_SHARED_SECRET=
```

`tool-secrets.env`:

```env
GIT_ACCESS_TOKEN=
GIT_PASSWORD=
GITHUB_TOKEN=
```

## 6. GitHub API plugin

GitHub API is an external verified plugin and is disabled until installed. Install it, enable the `github_api` profile, and store the token in `@tool_secrets` as `GITHUB_TOKEN`:

```bash
nagient plugin install nagient.github_api
nagient setup tool github_api --set token_secret=GITHUB_TOKEN
```

The plugin provides dedicated helpers and `nagient.github_api.request` for other GitHub REST endpoints, for example repository settings updates:

```bash
nagient tool invoke nagient.github_api.request \
  --tool-id github_api \
  --args-json '{"method":"PATCH","path":"/repos/OWNER/REPO","json":{"description":"Updated by Nagient"}}' \
  --auto-approve
```

`workspace_git` only inspects the configured `[workspace].root`. If it reports `git_repository=false`, check that the workspace root is the checkout mounted into the runtime, for example `@home/workspace` for the installed Docker layout or your repository path for local development.

`workspace_git` applies `author_name`, `author_email`, `committer_*`, `username`, and token/password secrets only to the git process it runs. It does not write your host-level global git config. Token/password auth is supplied through a temporary askpass helper for HTTPS remotes; SSH remotes still need normal SSH key access.

Delayed jobs have two direct-action helpers. Use `system.jobs.schedule_message` for prepared outbound text and `system.jobs.schedule_tool` for an exact stored tool request; both avoid waking the model again when the job is due. Keep `system.jobs.schedule_once` for self-wake jobs that genuinely need fresh model reasoning.

`system_config` exposes `system.config.read` and approval-gated `system.config.patch`, so the agent can inspect its runtime config and request explicit config edits.

## 7. First checks

- `safe_mode = true` in `runtime`
- `updates.base_url` points to your update center
- required provider is enabled via `nagient setup provider ...`
- matching provider key exists in `secrets.env`
- matching tool or connector key exists in `tool-secrets.env`
