# Переменные окружения

Язык: [English](env.md) | Русский

## 1. Переменные установщика

| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `NAGIENT_HOME` | Корень runtime | `~/.nagient` |
| `NAGIENT_CHANNEL` | Канал обновлений | `stable` |
| `NAGIENT_UPDATE_BASE_URL` | URL update center | задается release-установщиком |

Установщик также принимает `UPDATE_BASE_URL` как совместимый override, если вы запускаете уже сгенерированный скрипт вручную.

## 2. Переменные Docker Compose `.env`

Файл: `~/.nagient/.env`

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

## 3. Runtime-переменные (используются приложением)

### 3.1 Пути

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
