# AI Project Context

Этот файл предназначен не для конечного пользователя и не для маркетингового README. Он нужен другим AI-агентам и автоматизированным разработчикам, которые будут продолжать работу над проектом.

## 1. Намерение проекта

Nagient задуман как легковесный агент по типу OpenClaw-подхода, но без типичной ошибки “сначала соберём мозг, а потом как-нибудь задеплоим”. Здесь сначала поднимается delivery/control-plane слой, чтобы позже можно было спокойно собирать runtime, память, инструменты и пользовательские каналы без переделки системы доставки.

Пользовательский замысел проекта:

- агент должен устанавливаться через Docker image
- агент должен устанавливаться через shell-скрипт
- агент должен устанавливаться через PowerShell-скрипт
- релизы должны публиковаться автоматически
- обновления должны управляться централизованно
- миграции состояния должны быть встроены в модель обновлений
- в будущем уведомления об обновлениях должны приходить не только в CLI, но и через другие каналы, например Telegram, сайт, терминал и так далее

Иными словами: проект это не просто Python service, а будущая агентная платформа с унифицированной схемой распространения и обновления.

## 2. Что уже реализовано

На текущем этапе реализован infrastructure scaffold:

- пакет `nagient` с CLI
- settings/container/application/domain split
- bootstrap/reconcile cycle для runtime config
- transport plugin registry с built-in console/webhook/telegram
- transport scaffold generator для пользовательских Python plugins
- runtime-заглушка с heartbeat и activation report
- semver parser и comparer
- release/channel manifest entities
- parser и registry для manifests
- planner миграций
- shell и PowerShell install/update/uninstall scripts
- Dockerfile и docker-compose scaffold
- release manifest generator
- GitHub Actions для CI, release и Pages
- test suite для ключевых инфраструктурных контрактов

Это важно: кодовая база пока не реализует полноценного “умного” агента. Она реализует платформенный скелет, на который агент будет навешиваться дальше.

## 3. Структура репозитория

### Корневые файлы

- [pyproject.toml](../pyproject.toml): packaging, build backend, dev dependencies, tooling config
- [Makefile](../Makefile): developer entrypoints
- [Dockerfile](../Dockerfile): container runtime image
- [README.md](../README.md): краткая публичная шапка
- [README.ru.md](../README.ru.md): русская краткая шапка

### Код приложения

- [src/nagient/app/settings.py](../src/nagient/app/settings.py)
  runtime settings, env parsing, config TOML parsing, directory bootstrap
- [src/nagient/app/container.py](../src/nagient/app/container.py)
  dependency wiring
- [src/nagient/application/services/update_service.py](../src/nagient/application/services/update_service.py)
  update check orchestration
- [src/nagient/application/services/health_service.py](../src/nagient/application/services/health_service.py)
  diagnostics payload
- [src/nagient/infrastructure/registry.py](../src/nagient/infrastructure/registry.py)
  loading of channel/release manifests from filesystem or URL
- [src/nagient/infrastructure/manifests.py](../src/nagient/infrastructure/manifests.py)
  parsing and serialization of manifests
- [src/nagient/infrastructure/runtime.py](../src/nagient/infrastructure/runtime.py)
  current placeholder runtime loop
- [src/nagient/migrations/planner.py](../src/nagient/migrations/planner.py)
  linear migration planning based on version chain
- [src/nagient/cli.py](../src/nagient/cli.py)
  current command surface

### Delivery layer

- [scripts/install.sh](../scripts/install.sh)
- [scripts/update.sh](../scripts/update.sh)
- [scripts/uninstall.sh](../scripts/uninstall.sh)
- [scripts/install.ps1](../scripts/install.ps1)
- [scripts/update.ps1](../scripts/update.ps1)
- [scripts/uninstall.ps1](../scripts/uninstall.ps1)
- [scripts/release/build_release_manifest.py](../scripts/release/build_release_manifest.py)

### Release metadata

- [metadata/update-center/channels/stable.json](../metadata/update-center/channels/stable.json)
- [metadata/update-center/manifests/0.1.0.json](../metadata/update-center/manifests/0.1.0.json)
- [metadata/update-center/schema](../metadata/update-center/schema)

### Automation

- [.github/workflows/ci.yml](../.github/workflows/ci.yml)
- [.github/workflows/release.yml](../.github/workflows/release.yml)
- [.github/workflows/update-center.yml](../.github/workflows/update-center.yml)

### Tests

- [tests/unit](../tests/unit)
- [tests/integration](../tests/integration)
- [tests/smoke](../tests/smoke)
- [tests/fixtures/update_center](../tests/fixtures/update_center)

## 4. Инварианты, которые нельзя ломать без причины

Есть несколько контрактов, которые для проекта критичнее, чем любая частная реализация.

### 4.1 Update center contract

Установщики и CLI завязаны на две сущности:

1. `channels/<channel>.json`
2. `manifests/<version>.json`

`channels/<channel>.json` должен указывать на актуальный release manifest канала.

`manifests/<version>.json` должен содержать:

- версию
- канал
- дату публикации
- summary
- docker image
- список artifacts
- список migrations
- notices

Если AI-агент меняет schema или поля этих документов, он обязан одновременно:

- обновить parser в `src/nagient/infrastructure/manifests.py`
- обновить генерацию manifest в `src/nagient/cli.py` и/или `scripts/release/build_release_manifest.py`
- обновить shell и PowerShell installers
- обновить tests

### 4.2 Tag-driven delivery

Модель доставки основана на теге `vX.Y.Z`. Это не декоративное соглашение, а ядро release flow.

Тег должен соответствовать:

- Python package version
- Docker tag
- release manifest version
- published install assets
- stable channel pointer при очередном stable release

Если AI-агент меняет release flow, он не должен разрушать эту связность.

### 4.3 Centralized update logic

Обновление не должно определяться локальной магией инсталлятора. Источник правды должен оставаться централизованным. Это значит:

- install scripts читают channel manifest
- затем читают release manifest
- затем скачивают compose/install/update assets
- затем локально сохраняют metadata о текущем релизе

Не уводить проект в сторону “у каждого инсталлятора своя логика версий”.

### 4.4 Bootstrap and reconcile contract

Теперь у проекта есть ещё один важный контракт:

- `config.toml` хранит обычную runtime-конфигурацию
- `secrets.env` хранит transport/provider secrets
- `plugins/` хранит пользовательские Python transport plugins
- `nagient preflight` не пишет last-known-good, а только проверяет
- `nagient reconcile` пишет activation report и effective config
- `nagient serve` перед стартом обязан проходить через reconcile-cycle

Если AI-агент меняет bootstrap contract, он обязан одновременно обновить:

- `src/nagient/app/settings.py`
- `src/nagient/app/configuration.py`
- `src/nagient/application/services/preflight_service.py`
- `src/nagient/application/services/reconcile_service.py`
- Docker entrypoint
- install scripts
- tests

### 4.5 Transport plugin contract

Transport plugin больше не должен быть “просто произвольным модулем”.
Теперь контракт такой:

- plugin имеет manifest `plugin.toml`
- plugin имеет Python entrypoint
- plugin декларирует обязательные slot bindings
- plugin может иметь custom namespaced functions
- plugin должен проходить registry validation и self-tests
- ошибка transport plugin не должна падать в непойманный crash core-системы

## 5. Текущее CLI API

На сейчас доступны команды:

- `nagient version`
- `nagient init`
- `nagient status`
- `nagient doctor`
- `nagient preflight`
- `nagient reconcile`
- `nagient serve --once`
- `nagient transport list`
- `nagient transport scaffold`
- `nagient update check`
- `nagient manifest render`
- `nagient migrations plan`

Это не финальный UX. Это служебная поверхность для scaffolding, тестирования delivery-слоя и дальнейшего роста.

## 6. Что сейчас тестируется

Набор тестов страхует именно инфраструктуру:

- semver comparison
- manifest parsing/serialization
- settings loading
- config builder and secrets loading
- preflight/reconcile safe-mode behavior
- transport plugin registry and scaffold generation
- migration planning
- update service logic
- CLI update check
- CLI manifest render
- CLI init/preflight/reconcile/runtime flows
- наличие ключевых файлов репозитория
- bash syntax для shell scripts

Это означает, что при добавлении новых систем нужно продолжать мыслить контрактами. Если добавляется:

- runtime feature, нужен unit/integration test
- новый installer behavior, нужен smoke/integration test
- новая release metadata логика, нужен fixture-based test

## 7. Что ещё не реализовано

Ниже список крупных отсутствующих подсистем. Это реальный backlog, а не “может быть когда-нибудь”.

### 7.1 Agent core

Пока нет:

- scheduler / task loop
- prompt orchestration
- model provider abstraction
- tool execution runtime
- session lifecycle
- memory and persistence model
- structured task graph
- action planning and retries

### 7.2 External surfaces

Пока нет:

- HTTP API
- web dashboard
- TUI / richer terminal UX
- полноценный webhook/event bus
- полноценный Telegram bot runtime

### 7.3 Real migrations

Сейчас planner миграций существует, но реальные миграции состояния почти не реализованы. Пока это скорее proof of contract.

### 7.4 Real update notifications

Сейчас update center уже есть, но каналы доставки уведомлений пользователю ещё не построены.

## 8. Предпочтительный порядок дальнейшей разработки

Если AI-агенту нужно самостоятельно выбирать следующий полезный шаг, приоритет должен быть таким:

1. ввести runtime state model
2. ввести реальные persistent stores
3. добавить provider abstraction
4. реализовать task loop и agent execution cycle
5. добавить tool registry и sandbox-aware execution layer
6. затем уже внешние каналы и UI

Почему именно так: delivery infrastructure уже существует, а основной риск сейчас не в сборке, а в отсутствии реального агентного цикла.

## 9. Как безопасно вносить изменения

Другому AI-агенту лучше придерживаться таких правил:

- сначала читать существующие tests и workflow, потом менять код
- не удалять installer/update pipeline без явной необходимости
- не ломать `metadata/update-center` ради локального удобства
- не вводить тяжёлые зависимости без реальной пользы
- по возможности держать core на stdlib + минимальные runtime deps
- не размывать границы между application/domain/infrastructure без причины

Если меняется один из этих узлов, нужно проверить весь соседний контур:

- CLI
- scripts
- manifests
- tests
- release workflow

## 10. Что важно помнить про домен и Pages

Update center должен в будущем быть доступен по стабильному публичному URL. Идеальная схема:

- отдельный поддомен, например `updates.your-domain.tld`
- GitHub Pages как хостинг статических assets/manifests
- Docker Hub как контейнерный registry
- GitHub Releases как дополнительный канал артефактов

AI-агент не должен строить архитектуру так, будто обновления живут только внутри GitHub Releases. Releases полезны, но central update URL важнее.

## 11. Контекст по качеству и верификации

На момент подготовки scaffold локально были успешно пройдены:

- `unittest`
- smoke tests
- `ruff`
- `mypy`
- `python -m build --no-isolation`

Локально не были доступны `docker` и `pwsh`, поэтому соответствующие проверки в реальной среде ожидаются от CI.

## 12. Самый важный смысл проекта

Nagient не должен превратиться в “ещё один Python-скрипт с чат-командами”. Его сильная сторона должна быть в том, что:

- он легко ставится
- он централизованно обновляется
- его релизы воспроизводимы
- он может развиваться как платформа
- любые будущие каналы используют одну и ту же release/update модель

Если AI-агент сомневается между “быстро зашить фичу локально” и “сохранить централизованный контракт доставки”, приоритет почти всегда за вторым вариантом.
