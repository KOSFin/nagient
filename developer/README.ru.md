# Руководство для разработчиков

Язык: [English](README.md) | Русский

Этот документ описывает эксплуатацию репозитория, релизную автоматизацию и delivery-контракты.

## 1. Модель релизов

Модель релизов одновременно version-driven и tag-driven:

1. Версия задается в `src/nagient/version.py`.
2. `auto-tag.yml` читает версию при пуше в `main`.
3. Если тега `vX.Y.Z` нет, workflow создаёт его автоматически.
4. `release.yml` собирает и публикует package-артефакты и Docker image.
5. `update-center.yml` публикует metadata и установщики в Pages.

Ключевое поведение:

- Release не должен запускаться на каждый пуш в `main`.
- Release запускается только для новой версии без существующего тега.
- Публикация Pages принадлежит `update-center.yml` и выполняется из branch-контекста.

## 2. Централизованная конфигурация

`config/project.toml` — единый источник project defaults для рендера release-артефактов.

Релизная автоматика использует:

- `scripts/release/resolve_release_env.py`
- `scripts/release/render_release_assets.py`

Шаблоны переменных и примеры:

- `config/runtime.env.example`
- `config/github-actions.variables.example.env`
- `config/github-actions.secrets.example.env`

## 3. Runtime layout

Корень runtime: `~/.nagient`.

Основные файлы и каталоги:

- `config.toml`
- `secrets.env`
- `tool-secrets.env`
- `.env`
- `plugins/`
- `tools/`
- `state/activation-report.json`
- `state/effective-config.json`
- `state/last-known-good.json`

В рабочем проекте создается видимая `.nagient/` директория:

- `memory/`
- `notes/`
- `plans/`
- `jobs/`
- `scripts/`

## 4. GitHub variables и secrets

Repository Variables (`Settings -> Secrets and variables -> Actions -> Variables`):

| Имя | Назначение | Пример |
| --- | --- | --- |
| `UPDATE_BASE_URL` | Публичный URL update center | `https://updates.example.tld` |
| `CUSTOM_DOMAIN` | Hostname для `CNAME` | `updates.example.tld` |
| `DOCKERHUB_NAMESPACE` | Docker Hub namespace | `mydockerhubname` |
| `DOCKERHUB_IMAGE_NAME` | Имя Docker image | `nagient` |

Repository Secrets (`Settings -> Secrets and variables -> Actions -> Secrets`):

| Имя | Назначение |
| --- | --- |
| `DOCKERHUB_USERNAME` | Логин Docker Hub |
| `DOCKERHUB_TOKEN` | Access token Docker Hub |

## 5. Локальная разработка

Рекомендуемая версия Python: `3.12`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Проверки качества:

```bash
make test PYTHON=python3.12
make smoke PYTHON=python3.12
PYTHONPATH=src python3.12 -m ruff check src tests scripts/release
PYTHONPATH=src python3.12 -m mypy src
PYTHONPATH=src python3.12 -m build --no-isolation
```

## 6. Bootstrap и reconcile

Операционный цикл:

```bash
PYTHONPATH=src python3.12 -m nagient init
PYTHONPATH=src python3.12 -m nagient preflight --format json
PYTHONPATH=src python3.12 -m nagient reconcile --format json
PYTHONPATH=src python3.12 -m nagient status --format json
```

Назначение команд:

- `init`: создает runtime defaults и базовую структуру каталогов.
- `preflight`: валидирует конфиг, плагины, секреты и health checks.
- `reconcile`: выполняет activation-cycle и сохраняет snapshots.
- `status`: показывает эффективное состояние и диагностику.

По умолчанию включен safe mode (`runtime.safe_mode = true`).

## 7. Чеклист релиза

1. Обновить `src/nagient/version.py`.
2. Если менялся delivery-контракт, обновить renderers и тесты.
3. Прогнать локальные quality gates.
4. Запушить в `main`.
5. Проверить, что `auto-tag.yml` создал `vX.Y.Z`.
6. Проверить, что `release.yml` опубликовал артефакты и Docker image.
7. Проверить, что `update-center.yml` обновил Pages metadata.

Если тег `vX.Y.Z` уже существует, auto-tag пропускает повторное создание, и новый release-run не ожидается.

## 8. Матрица изменений

| Что меняется | Где править |
| --- | --- |
| версия релиза | `src/nagient/version.py` |
| project defaults | `config/project.toml` |
| sample runtime config | `config/nagient.example.toml` |
| samples для runtime secrets | `config/secrets.example.env`, `config/tool-secrets.example.env` |
| samples для workflow variables | `config/github-actions.variables.example.env` |
| samples для workflow secrets | `config/github-actions.secrets.example.env` |
| resolve release env | `scripts/release/resolve_release_env.py` |
| render release assets | `scripts/release/render_release_assets.py` |
| install/update scripts | `scripts/` |
| settings и пути runtime | `src/nagient/app/settings.py`, `src/nagient/app/configuration.py` |
| логика сервисов | `src/nagient/application/services/` |
| GitHub automation | `.github/workflows/` |

## 9. Ограничения и инварианты

- Сохранять стабильный update center contract (`channels/<channel>.json`, `manifests/<version>.json`).
- Не добавлять placeholder-домены в публикуемые артефакты.
- Держать релизный процесс tag-driven и воспроизводимым.
- Синхронизировать transport/provider/tool/workspace контракты с тестами.
