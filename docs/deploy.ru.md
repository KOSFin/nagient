# Развёртывание через Docker Compose

Язык: [English](deploy.md) | Русский

Это руководство описывает развёртывание Nagient на своём сервере через Docker
Compose без хостед-установщика. Подходит, когда нужен полный контроль над
рантаймом или когда машина не может достучаться до центра обновлений.

## Требования

- Docker Engine 24+
- Docker Compose v2 (`docker compose`, не устаревший `docker-compose`)
- API-ключ провайдера (OpenAI, Anthropic, Gemini, DeepSeek или локальный Ollama)

## 1. Получить compose-файл

Склонируйте репозиторий (или скопируйте `docker-compose.yml` и `.env.example` на
сервер):

```bash
git clone https://github.com/KOSFin/nagient.git
cd nagient
```

## 2. Настройка через переменные окружения

Скопируйте пример и задайте всё необходимое рантайму в одном файле:

```bash
cp .env.example .env
chmod 600 .env
```

Например, для OpenAI и Telegram достаточно раскомментировать в `.env`:

```dotenv
NAGIENT_AGENT_DEFAULT_PROVIDER=openai
NAGIENT_AGENT_REQUIRE_PROVIDER=true
NAGIENT_PROVIDER__OPENAI__PLUGIN=builtin.openai
NAGIENT_PROVIDER__OPENAI__ENABLED=true
NAGIENT_PROVIDER__OPENAI__AUTH=api_key
NAGIENT_PROVIDER__OPENAI__API_KEY_SECRET=OPENAI_API_KEY
NAGIENT_PROVIDER__OPENAI__MODEL=gpt-4.1-mini
OPENAI_API_KEY=sk-...

NAGIENT_TRANSPORT__CONSOLE__ENABLED=false
NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=builtin.telegram
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
NAGIENT_TRANSPORT__TELEGRAM__DEFAULT_CHAT_ID=123456789
TELEGRAM_BOT_TOKEN=123456:ABC...
```

Compose передаёт весь `.env` внутрь контейнера. Запускать `nagient setup`,
редактировать TOML или сгенерированный файл секретов не требуется.

## 3. Первый запуск

```bash
docker compose up -d
```

При первом запуске контейнер также создаёт совместимые файлы в `./data`. Они
нужны для persistent- и CLI-сценариев, но переменные окружения имеют приоритет,
поэтому вручную работать с этими файлами не требуется.

## 4. Проверка

```bash
docker compose exec nagient nagient status
docker compose exec nagient nagient doctor --format json
docker compose logs -f nagient
```

`nagient doctor` также используется в healthcheck контейнера, поэтому
`docker compose ps` покажет `healthy`, когда рантайм готов.

## Расположение данных

Всё хранится в двух каталогах на хосте, оба легко бэкапить:

- `./data` — конфиг, секреты, состояние, логи, учётные данные и установленные плагины.
- `./workspace` — ограниченный workspace, в котором агент читает и пишет.

## Модель конфигурации

Любое текущее поле конфигурации доступно без CLI:

- общие настройки задаются через `NAGIENT_SAFE_MODE`,
  `NAGIENT_WORKSPACE_MODE`, `NAGIENT_AGENT__MAX_TURNS` и аналогичные переменные;
- поля провайдеров, транспортов и инструментов задаются как
  `NAGIENT_PROVIDER__<ID>__<FIELD>`, `NAGIENT_TRANSPORT__<ID>__<FIELD>` и
  `NAGIENT_TOOL__<ID>__<FIELD>`;
- связанные секреты (`OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN` и произвольные
  имена секретов плагинов) читаются прямо из окружения контейнера;
- `NAGIENT_CONFIG_JSON` позволяет передать полный TOML-образный JSON для
  вложенных и будущих полей;
- `NAGIENT_SECRETS_JSON` и `NAGIENT_TOOL_SECRETS_JSON` принимают произвольные
  JSON-объекты с секретами.

Приоритет: отдельные env-переменные, JSON-конфигурация из env, persistent-файлы,
встроенные значения. Полный справочник: [env.ru.md](env.ru.md).

Чтобы использовать env-файл с другим именем:

```bash
NAGIENT_ENV_FILE=/srv/nagient/production.env \
  docker compose --env-file /srv/nagient/production.env up -d
```

## Обновление

Закрепите новый тег в `.env` (или оставьте `:latest`) и обновитесь:

```bash
docker compose pull
docker compose up -d
```

## Удаление

```bash
docker compose down
```

Чтобы удалить и данные рантайма, удалите каталоги на хосте:

```bash
rm -rf ./data ./workspace
```

## Доступ к webhook

По умолчанию Compose публикует порт webhook на `127.0.0.1:8080`. Задавайте
`NAGIENT_WEBHOOK_BIND_ADDRESS=0.0.0.0` и
`NAGIENT_WEBHOOK_PORT=<порт-на-хосте>` только когда внешний доступ действительно
нужен, а endpoint защищён firewall или reverse proxy.
