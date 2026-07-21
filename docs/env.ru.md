# Переменные окружения

Язык: [English](env.md) | Русский

## 1. Переменные установщика

| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `NAGIENT_HOME` | Корень runtime | `~/.nagient` |
| `NAGIENT_CHANNEL` | Канал обновлений | `stable` |
| `NAGIENT_UPDATE_BASE_URL` | URL update center | задается release-установщиком |

Установщик также принимает `UPDATE_BASE_URL` как совместимый override, если вы запускаете уже сгенерированный скрипт вручную.

## 2. Env-only запуск через Docker Compose

Корневой `docker-compose.yml` передаёт весь `.env` внутрь контейнера. Для файла
с другим именем задайте `NAGIENT_ENV_FILE` перед `docker compose up`.

| Переменная | Назначение | Пример |
| --- | --- | --- |
| `NAGIENT_IMAGE` | Тег контейнера | `docker.io/parampo/nagient:0.1.0` |
| `NAGIENT_CHANNEL` | Канал обновлений | `stable` |
| `NAGIENT_UPDATE_BASE_URL` | Базовый URL update center | `https://ngnt-in.ruka.me` |
| `NAGIENT_CONTAINER_NAME` | Имя контейнера | `nagient` |
| `NAGIENT_DOCKER_PROJECT_NAME` | Имя compose-проекта | `nagient` |
| `NAGIENT_SAFE_MODE` | Safe mode | `true` |
| `NAGIENT_WORKSPACE_ROOT` | Рабочая директория | `/workspace` |
| `NAGIENT_HEARTBEAT_INTERVAL` | Heartbeat в секундах | `30` |
| `NAGIENT_WEBHOOK_BIND_ADDRESS` | Интерфейс хоста для webhook | `127.0.0.1` |
| `NAGIENT_WEBHOOK_PORT` | Публикуемый порт webhook | `8080` |
| `NAGIENT_PLUGIN_SPECS` | Git-репозитории внешних плагинов | пусто |

## 3. Runtime-переменные (используются приложением)

### 3.1 Пути

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

### 3.2 Поведение runtime

- `NAGIENT_CHANNEL`
- `NAGIENT_UPDATE_BASE_URL`
- `NAGIENT_HEARTBEAT_INTERVAL`
- `NAGIENT_DOCKER_PROJECT_NAME`
- `NAGIENT_SAFE_MODE`

### 3.3 Workspace и агент

- `NAGIENT_WORKSPACE_ROOT`
- `NAGIENT_WORKSPACE_MODE` (`bounded` или `unsafe`)
- `NAGIENT_AGENT_DEFAULT_PROVIDER`
- `NAGIENT_AGENT_REQUIRE_PROVIDER`
- `NAGIENT_AGENT__<FIELD>` для любого прямого поля `[agent]`, например
  `NAGIENT_AGENT__MAX_TURNS=20`
- `NAGIENT_AGENT_MEMORY__<FIELD>`
- `NAGIENT_AGENT_LOGGING__<FIELD>`
- `NAGIENT_AGENT_PROGRESS__<FIELD>`

## 4. Dynamic overrides провайдеров, транспортов и инструментов

Поля конкретного плагина описаны в его манифесте и доступны через
`nagient plugin catalog list --format json`. Для всех расширений действует одна
схема: `NAGIENT_<FAMILY>__<PLUGIN_ID>__<FIELD>`.

Provider override:

```env
NAGIENT_PROVIDER__OPENAI__ENABLED=true
NAGIENT_PROVIDER__OPENAI__MODEL=gpt-4.1-mini
```

Transport override:

```env
NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=nagient.telegram
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
NAGIENT_TRANSPORT__TELEGRAM__DEFAULT_CHAT_ID=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS=-1001234567890,123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=private,supergroup
NAGIENT_TRANSPORT__TELEGRAM__PROXY_URL=http://proxy.example:8080
NAGIENT_TRANSPORT__TELEGRAM__PROXY_USERNAME=proxy-user
NAGIENT_TRANSPORT__TELEGRAM__PROXY_PASSWORD_SECRET=TELEGRAM_PROXY_PASSWORD
TELEGRAM_PROXY_PASSWORD=...
```

`PROXY_URL` применяется ко всем обращениям Telegram Bot API: polling, отправке
сообщений и callback-методам. Поддерживаются HTTP- и HTTPS-прокси. Логин можно
указать в `PROXY_USERNAME`, а пароль — только через секрет. Если прокси уже
содержит `http://user:password@host:port`, отдельные поля авторизации не нужны,
но такой URL нельзя помещать в публичный репозиторий.

Tool override:

```env
NAGIENT_TOOL__GITHUB_API__PLUGIN=nagient.github_api
NAGIENT_TOOL__GITHUB_API__ENABLED=true
NAGIENT_TOOL__GITHUB_API__TOKEN_SECRET=GITHUB_TOKEN
NAGIENT_TOOL__GITHUB_API__BASE_URL=https://api.github.com
NAGIENT_TOOL__WORKSPACE_GIT__AUTHOR_NAME=Nagient Agent
NAGIENT_TOOL__WORKSPACE_GIT__AUTHOR_EMAIL=agent@example.com
NAGIENT_TOOL__WORKSPACE_GIT__USERNAME=git-user
NAGIENT_TOOL__WORKSPACE_GIT__TOKEN_SECRET=GIT_ACCESS_TOKEN
```

ID и имена полей в переменных регистронезависимы. ID провайдера с дефисом можно
записать через подчёркивание: `OPENAI_CODEX` сопоставится существующему профилю
`openai-codex`.

## 5. Секреты из окружения

Если поле провайдера, транспорта или инструмента ссылается на имя секрета,
одноимённая переменная читается прямо из окружения контейнера:

```env
NAGIENT_PROVIDER__OPENAI__API_KEY_SECRET=OPENAI_API_KEY
OPENAI_API_KEY=sk-...
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN=123456:ABC...
```

Для произвольных имён можно использовать JSON-объекты:

```env
NAGIENT_SECRETS_JSON={"CUSTOM_PROVIDER_KEY":"value"}
NAGIENT_TOOL_SECRETS_JSON={"CUSTOM_TOOL_TOKEN":"value"}
```

## 6. Провайдеры и ключи

Встроенные профили используют одинаковую схему. Меняется только ID профиля,
модель и имя ключа:

| Профиль | Плагин | Переменная ключа |
| --- | --- | --- |
| `openai` | `builtin.openai` | `OPENAI_API_KEY` |
| `openai-codex` | `builtin.openai_codex` | ключ или auth-файл Codex |
| `anthropic` | `builtin.anthropic` | `ANTHROPIC_API_KEY` |
| `deepseek` | `builtin.deepseek` | `DEEPSEEK_API_KEY` |
| `gemini` | `builtin.gemini` | `GEMINI_API_KEY` |
| `ollama` | `builtin.ollama` | ключ не нужен |

Минимальный пример для DeepSeek:

```env
NAGIENT_AGENT_DEFAULT_PROVIDER=deepseek
NAGIENT_AGENT_REQUIRE_PROVIDER=true
NAGIENT_PROVIDER__DEEPSEEK__PLUGIN=builtin.deepseek
NAGIENT_PROVIDER__DEEPSEEK__ENABLED=true
NAGIENT_PROVIDER__DEEPSEEK__AUTH=api_key
NAGIENT_PROVIDER__DEEPSEEK__API_KEY_SECRET=DEEPSEEK_API_KEY
NAGIENT_PROVIDER__DEEPSEEK__MODEL=deepseek-chat
DEEPSEEK_API_KEY=...
```

Плагин может объявить собственные поля в манифесте. Для них действует тот же
шаблон `NAGIENT_<FAMILY>__<ID>__<FIELD>`, поэтому отдельный код в Compose не
нужен.

## 7. Полная JSON-конфигурация

`NAGIENT_CONFIG_JSON` принимает JSON с той же иерархией, что и `config.toml`.
Объекты объединяются рекурсивно, поэтому через эту переменную доступны любые
существующие вложенные поля и будущие настройки плагинов:

```env
NAGIENT_CONFIG_JSON={"agent":{"max_turns":20,"progress":{"enabled":true}},"workspace":{"mode":"bounded"}}
```

Приоритет, от самого высокого:

1. отдельные env-переменные;
2. `NAGIENT_CONFIG_JSON` и JSON-переменные секретов;
3. persistent-файлы `config.toml`, `secrets.env`, `tool-secrets.env`;
4. встроенные значения.
