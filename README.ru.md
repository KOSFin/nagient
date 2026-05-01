# Nagient

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-native-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![Releases](https://img.shields.io/badge/Releases-tag--driven-F97316?logo=git&logoColor=white)](.github/workflows/release.yml)
[![Update Center](https://img.shields.io/badge/Update%20Center-Pages%20ready-222222?logo=githubpages&logoColor=white)](.github/workflows/update-center.yml)
[![Auto Tag](https://img.shields.io/badge/Tags-auto--create-111827?logo=git&logoColor=white)](.github/workflows/auto-tag.yml)
[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-parampo%2Fnagient-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/parampo/nagient)
[![License](https://img.shields.io/badge/License-MIT-16A34A.svg)](LICENSE)

🇷🇺 Русский | 🇺🇸 [English](README.md)

Docker-native агентная платформа с централизованными обновлениями, скриптовой установкой и релизами по тегам.

Nagient рассчитан на предсказуемый запуск и обновления на Linux, macOS и Windows.

## Установка последней стабильной версии

### Linux и macOS

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

### Docker image

```bash
docker pull docker.io/parampo/nagient:latest
```

Установщик создаёт локальный runtime в `~/.nagient` и поднимает сервис через Docker Compose.

После установки используйте одну короткую команду управления:

```bash
~/.nagient/bin/nagient help
```

Подробная документация:

- Индекс на английском: [docs/README.md](docs/README.md)
- Индекс на русском: [docs/README.ru.md](docs/README.ru.md)

## Обновление и удаление

Через короткую команду:

```bash
~/.nagient/bin/nagient update
```

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" update
```

Удаление:

```bash
~/.nagient/bin/nagient remove
```

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" remove
```

Чтобы удалить и контейнеры, и локальные файлы, перед удалением задайте `NAGIENT_PURGE=true`.

## Быстрый старт

1. Запустите установщик под вашу платформу.
2. Запустите `nagient setup`.
3. Используйте `nagient paths`, чтобы увидеть алиасы вроде `@config` и `@secrets`.
4. Используйте `nagient chat` для прямой CLI-сессии с настроенным provider.
5. Используйте короткие команды.

```bash
~/.nagient/bin/nagient up
~/.nagient/bin/nagient status
~/.nagient/bin/nagient logs
```

## Короткий набор команд

- `nagient up|down|restart`
- `nagient status|doctor|preflight|reconcile`
- `nagient logs [service]`
- `nagient update|remove`

## Полный CLI-набор

- `nagient init`, `nagient paths`, `nagient preflight`, `nagient reconcile`, `nagient serve`
- `nagient setup`, `nagient chat`
- `nagient transport list|test|scaffold`
- `nagient provider list|scaffold|models`
- `nagient auth status|login|complete|logout`
- `nagient tool list|scaffold|invoke`
- `nagient interaction list|submit`, `nagient approval list|respond`
- `nagient update check`, `nagient manifest render`, `nagient migrations plan`
- `nagient agent turn --request-file ...`

Полный справочник с параметрами находится в [docs/README.md](docs/README.md).

## Runtime-схема

```mermaid
flowchart LR
	A[Install script] --> B[~/.nagient]
	B --> C[docker compose up -d]
	C --> D[entrypoint]
	D --> E[nagient reconcile]
	E --> F[nagient serve]
	F --> G[state and logs]
```

## Дополнительно

- Архитектура (RU): [docs/architecture.ru.md](docs/architecture.ru.md)
- Архитектура (EN): [docs/architecture.md](docs/architecture.md)
- Лицензия: [LICENSE](LICENSE)
