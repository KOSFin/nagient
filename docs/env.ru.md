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

## 6. Полная JSON-конфигурация

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
