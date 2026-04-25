# Configuration

## 1. Где лежит runtime

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
~/.nagient/bin/nagientctl preflight
~/.nagient/bin/nagientctl reconcile
~/.nagient/bin/nagientctl status
```

## 3. Пример config.toml

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

## 4. Secrets

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

## 5. Что проверять первым делом

- `safe_mode = true` в `runtime`
- правильно ли указан `updates.base_url`
- включен ли нужный `providers.<id>.enabled = true`
- есть ли соответствующий ключ в `secrets.env`
