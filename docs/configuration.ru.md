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
  plugins/
  tools/
  providers/
  credentials/
  runtime/
  releases/
```

## 2. Минимальный рабочий сценарий

1. Установить Nagient.
2. Открыть `~/.nagient/config.toml`.
3. Включить нужного provider.
4. Добавить секрет в `~/.nagient/secrets.env`.
5. Выполнить:

```bash
~/.nagient/bin/nagient preflight
~/.nagient/bin/nagient reconcile
~/.nagient/bin/nagient status
```

## 3. Пример `config.toml`

```toml
[updates]
channel = "stable"
base_url = "https://ngnt-in.ruka.me"

[runtime]
heartbeat_interval_seconds = 30
safe_mode = true

[docker]
project_name = "nagient"

[workspace]
root = ""
mode = "bounded"

[agent]
default_provider = "openai"
require_provider = true

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

[tools.workspace_git]
plugin = "workspace.git"
enabled = true
```

## 4. Секреты

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
GITHUB_TOKEN=
```

## 5. Что проверить в первую очередь

- `safe_mode = true` в секции `runtime`
- корректный `updates.base_url`
- нужный provider включен через `providers.<id>.enabled = true`
- соответствующий ключ есть в `secrets.env`
