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

## 2. Настройка (необязательно)

Значения по умолчанию работают сразу. Чтобы закрепить конкретную версию образа
или переименовать контейнер, скопируйте пример env-файла и отредактируйте его:

```bash
cp .env.example .env
```

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `NAGIENT_IMAGE` | `docker.io/parampo/nagient:latest` | Образ и тег. В проде закрепляйте версию, например `:0.8.8`. |
| `NAGIENT_CONTAINER_NAME` | `nagient` | Имя контейнера. |
| `NAGIENT_HEARTBEAT_INTERVAL` | `30` | Интервал записи heartbeat, секунды. |
| `NAGIENT_SAFE_MODE` | `true` | Оставляет защиту путей workspace включённой. |

## 3. Первый запуск

```bash
docker compose up -d
```

При первом запуске контейнер создаёт `config.toml` и `secrets.env` в `./data` на
хосте. Заранее создавать файлы не нужно.

## 4. Добавить секреты

Отредактируйте `./data/secrets.env` и добавьте ключи провайдеров и транспортов,
которые собираетесь использовать:

```dotenv
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC...
```

## 5. Включить провайдер и транспорт

Отредактируйте `./data/config.toml`:

```toml
[agent]
default_provider = "openai"

[providers.openai]
enabled = true

[transports.telegram]
enabled = true
default_chat_id = "123456789"
```

Затем примените изменения:

```bash
docker compose restart
```

## 6. Проверка

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

## Примечания

- Секреты читаются из `./data/secrets.env`, а не из переменных окружения
  оболочки. Не добавляйте этот файл в систему контроля версий.
- Чтобы открыть webhook-транспорт, добавьте `ports:` в сервис `nagient` и
  включите `[transports.webhook]` в `config.toml`.
