# Nagient

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-native-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![Releases](https://img.shields.io/badge/Releases-tag--driven-F97316?logo=git&logoColor=white)](.github/workflows/release.yml)
[![Update Center](https://img.shields.io/badge/Update%20Center-Pages%20ready-222222?logo=githubpages&logoColor=white)](.github/workflows/update-center.yml)
[![Auto Tag](https://img.shields.io/badge/Tags-auto--create-111827?logo=git&logoColor=white)](.github/workflows/auto-tag.yml)
[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-auto--publish-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-16A34A.svg)](LICENSE)
[![Dev Guide](https://img.shields.io/badge/Docs-Developer-0F766E)](developer/README.md)
[![AI Context](https://img.shields.io/badge/Docs-AI-7C3AED)](ai/README.md)

🇷🇺 Русский | 🇺🇸 [English](README.md)

> Легковесная Docker-native агентная платформа с централизованными обновлениями, скриптовой установкой и релизами по тегам.

Nagient строится как лёгкий агент с нормальной системой доставки с первого дня: Docker image, установщики `sh` и `ps1`, централизованный update center и CI/CD вокруг tag-based релизов.

Основная агентная сборка ещё в процессе. Зато платформа вокруг неё уже поднята: release automation, update center, install/update-скрипты, Docker runtime scaffold, тестовые контуры и структура репозитория для дальнейшей разработки.

## Быстрые ссылки

- 🧑‍💻 [Гайд для разработчика](developer/README.md)
- 🤖 [Контекст для AI-агентов](ai/README.md)
- 🏗️ [Архитектурные заметки](docs/architecture.ru.md)

## Поверхность установки

```bash
docker pull docker.io/<dockerhub-namespace>/nagient:<tag>
curl -fsSL <update-base-url>/<tag>/install.sh | bash
pwsh -Command "iwr <update-base-url>/<tag>/install.ps1 -UseBasicParsing | iex"
```

Вся эксплуатационная документация, переменные, release flow и настройка домена вынесены в [developer/README.md](developer/README.md).
