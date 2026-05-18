# Конфигурация

Язык: [English](configuration.md) | Русский

## 1. Расположение runtime

Базовый путь: `~/.nagient`

Структура:

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

## 2. Минимальный рабочий сценарий

1. Установить Nagient.
2. Запустить `~/.nagient/bin/nagient setup`.
3. Настроить provider, transport, workspace и секреты через меню setup.
4. Использовать `~/.nagient/bin/nagient paths`, когда нужны точные пути после раскрытия алиасов.
5. Выполнить:

```bash
~/.nagient/bin/nagient preflight
~/.nagient/bin/nagient reconcile
~/.nagient/bin/nagient status
```

## 3. Алиасы путей

Конфиг и setup-подсказки принимают каноничные алиасы:

- `@home`, `@config`, `@secrets`, `@tool_secrets`, `@prompts`
- `@plugins`, `@tools`, `@providers`, `@credentials`
- `@state`, `@logs`, `@releases`

## 4. Пример `config.toml`

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
```

## 5. Секреты

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

## 6. Встроенный GitHub tool

Профиль `github_api` есть из коробки и выключен до настройки. Он умеет читать репозитории, получать issues, создавать issues, писать комментарии и выполнять общий `github.api.request`. Сохраните токен в `@tool_secrets` как `GITHUB_TOKEN`, затем включите tool:

```bash
~/.nagient/bin/nagient setup tool github_api --enable --set token_secret=GITHUB_TOKEN
```

Используйте `github.api.request` для GitHub REST endpoints, для которых пока нет отдельного helper, например для обновления настроек репозитория:

```bash
~/.nagient/bin/nagient tool invoke github.api.request \
  --tool-id github_api \
  --args-json '{"method":"PATCH","path":"/repos/OWNER/REPO","json":{"description":"Updated by Nagient"}}' \
  --auto-approve
```

`workspace_git` проверяет только настроенный `[workspace].root`. Если он возвращает `git_repository=false`, проверьте, что workspace root указывает на checkout, смонтированный в runtime: например `@home/workspace` для установленного Docker layout или путь к репозиторию при локальной разработке.

## 7. Что проверить в первую очередь

- `safe_mode = true` в секции `runtime`
- корректный `updates.base_url`
- нужный provider включен через `nagient setup provider ...`
- соответствующий provider-ключ есть в `secrets.env`
- соответствующий tool/connector-ключ есть в `tool-secrets.env`
