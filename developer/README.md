# Developer Guide

Этот файл про эксплуатацию репозитория и delivery-слой проекта. Главный `README` intentionally короткий; всё важное для разработки и публикации собрано здесь.

## С чего теперь работает релиз

Текущая схема полностью завязана на версии в [src/nagient/version.py](../src/nagient/version.py) и на централизованном конфиге [config/project.toml](../config/project.toml).

Что происходит после пуша в `main`:

1. `auto-tag.yml` читает версию проекта.
2. Если тега `vX.Y.Z` ещё нет, workflow создаёт его сам.
3. После создания нового тега `auto-tag.yml` сразу диспатчит `release.yml` на этот тег.
4. `release.yml` собирает package, Docker image и GitHub release assets.
5. `update-center.yml` публикует update center в GitHub Pages из `main`.

Ключевое правило:

- `Release` не должен запускаться на каждый пуш в `main`.
- Он запускается только когда версия в [src/nagient/version.py](../src/nagient/version.py) изменилась и для неё ещё нет тега.
- Если тег уже существует, `Auto Tag` завершится успешно, но релиз будет осознанно пропущен.
- GitHub Pages не деплоится из тега: Pages теперь принадлежит только `update-center.yml`, потому что environment `github-pages` обычно защищают по branch rules, а не по тегам.

То есть вручную создавать теги больше не нужно. Достаточно:

1. изменить [src/nagient/version.py](../src/nagient/version.py)
2. закоммитить
3. запушить в `main`

## Где теперь лежат настройки

### Централизованный repo config

Файл [config/project.toml](../config/project.toml) это единая база для:

- slug проекта
- display name
- default channel
- runtime defaults
- docker/project naming

Workflow-ы не дублируют эту логику вручную. Они используют:

- [scripts/release/resolve_release_env.py](../scripts/release/resolve_release_env.py)
- [scripts/release/render_release_assets.py](../scripts/release/render_release_assets.py)

### Runtime env example

Локальные runtime-переменные собраны в [config/runtime.env.example](../config/runtime.env.example).

Их можно:

- экспортировать в shell
- положить в локальный `.env`
- использовать как основу для Docker Compose env file

### GitHub variables / secrets examples

Примеры значений для GitHub лежат в:

- [config/github-actions.variables.example.env](../config/github-actions.variables.example.env)
- [config/github-actions.secrets.example.env](../config/github-actions.secrets.example.env)

### Runtime files

Единый bootstrap/runtime layout теперь такой:

- `config.toml`: обычная конфигурация runtime, transport instances, safe mode
- `secrets.env`: секреты transport/provider уровня
- `plugins/`: пользовательские Python transport plugins
- `state/activation-report.json`: последний результат `nagient reconcile`
- `state/effective-config.json`: последняя успешно активированная конфигурация
- `state/last-known-good.json`: last-known-good snapshot

## Что и куда вставлять в GitHub

### Repository Variables

Открой:

`Settings -> Secrets and variables -> Actions -> Variables`

И создай переменные:

| Имя | Что туда вставлять | Пример |
| --- | --- | --- |
| `UPDATE_BASE_URL` | полный публичный URL update center, можно с путём | `https://updates.your-domain.tld` |
| `CUSTOM_DOMAIN` | только hostname без `https://` и без пути | `updates.your-domain.tld` |
| `DOCKERHUB_NAMESPACE` | namespace или username в Docker Hub | `mydockerhubname` |
| `DOCKERHUB_IMAGE_NAME` | имя образа | `nagient` |

Очень важный момент:

- `UPDATE_BASE_URL` это полный URL, его читают manifests и install/update scripts.
- `CUSTOM_DOMAIN` это только домен для `CNAME`, без пути.

Если update center публикуется в корень домена:

```text
UPDATE_BASE_URL=https://updates.your-domain.tld
CUSTOM_DOMAIN=updates.your-domain.tld
```

Если он публикуется в подпуть:

```text
UPDATE_BASE_URL=https://updates.your-domain.tld/nagient
CUSTOM_DOMAIN=updates.your-domain.tld
```

### Repository Secrets

Открой:

`Settings -> Secrets and variables -> Actions -> Secrets`

И создай секреты:

| Имя | Что туда вставлять |
| --- | --- |
| `DOCKERHUB_USERNAME` | логин Docker Hub |
| `DOCKERHUB_TOKEN` | access token Docker Hub |

Без этих секретов release workflow соберёт образ, но не сможет его опубликовать в Docker Hub.
Если секреты заданы и в логе есть `push: true`, но job потом упал на другом шаге, это не отменяет уже выполненный Docker push.

## Runtime переменные и где они используются

| Переменная | Где используется | Значение по умолчанию |
| --- | --- | --- |
| `NAGIENT_HOME` | локальная рабочая директория | `~/.nagient` |
| `NAGIENT_CONFIG` | путь до TOML-конфига | `~/.nagient/config.toml` |
| `NAGIENT_SECRETS_FILE` | путь до `secrets.env` | `~/.nagient/secrets.env` |
| `NAGIENT_PLUGINS_DIR` | каталог пользовательских transport plugins | `~/.nagient/plugins` |
| `NAGIENT_STATE_DIR` | state / heartbeat | `~/.nagient/state` |
| `NAGIENT_LOG_DIR` | лог-файлы | `~/.nagient/logs` |
| `NAGIENT_RELEASES_DIR` | локально сохранённые manifests | `~/.nagient/releases` |
| `NAGIENT_CHANNEL` | канал обновлений | `stable` |
| `NAGIENT_UPDATE_BASE_URL` | публичный URL update center | пусто, пока не задано |
| `NAGIENT_HEARTBEAT_INTERVAL` | heartbeat interval | `30` |
| `NAGIENT_DOCKER_PROJECT_NAME` | docker compose project name | `nagient` |
| `NAGIENT_SAFE_MODE` | блокировать запуск при ошибках transport checks | `true` |

Что важно понимать:

- в исходниках репозитория install/update scripts и compose файл больше не содержат фейковых доменов.
- release workflow рендерит publish-ready assets с реальным `UPDATE_BASE_URL`.
- если запускать сырой `scripts/install.sh` прямо из checkout без env, он теперь честно упадёт с сообщением “настрой URL”.

## Локальный старт

Рекомендуемая версия Python: `3.12`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Проверка проекта:

```bash
make test PYTHON=python3.12
make smoke PYTHON=python3.12
PYTHONPATH=src python3.12 -m ruff check src tests scripts/release
PYTHONPATH=src python3.12 -m mypy src
PYTHONPATH=src python3.12 -m build --no-isolation
```

## Bootstrap и reconcile

Теперь базовый операционный цикл такой:

```bash
PYTHONPATH=src python3.12 -m nagient init
PYTHONPATH=src python3.12 -m nagient preflight --format json
PYTHONPATH=src python3.12 -m nagient reconcile --format json
PYTHONPATH=src python3.12 -m nagient status --format json
```

Что делают команды:

- `init`: создаёт `config.toml`, `secrets.env` и `plugins/README.md`
- `preflight`: проверяет конфиг, transport plugins, secret refs и self-tests без активации
- `reconcile`: прогоняет тот же цикл и сохраняет last-known-good/effective snapshots
- `status`: показывает paths, activation report и статус update center
- `transport scaffold --plugin-id your.plugin.id`: генерирует пользовательский transport template

Safe mode включен по умолчанию. Если enabled transports не проходят проверки, `reconcile` и `serve` завершаются ошибкой. Его можно выключить через `NAGIENT_SAFE_MODE=false` или `runtime.safe_mode = false`, тогда runtime поднимется в `degraded` состоянии.

## Docker Compose layout

Сгенерированный compose now expects рядом с `docker-compose.yml`:

- `config.toml`
- `secrets.env`
- `plugins/`
- `runtime/`

Практический цикл пользователя:

1. Запустить installer или скопировать release `docker-compose.yml`.
2. Отредактировать `config.toml` и `secrets.env`.
3. При необходимости положить пользовательский plugin в `plugins/<plugin-id>/`.
4. Выполнить `docker compose up -d`.
5. Контейнер при старте автоматически вызовет `nagient reconcile`.

## Что меняется где

| Что нужно поменять | Где править |
| --- | --- |
| версия релиза | [src/nagient/version.py](../src/nagient/version.py) |
| централизованные project defaults | [config/project.toml](../config/project.toml) |
| runtime config sample | [config/nagient.example.toml](../config/nagient.example.toml) |
| runtime secrets sample | [config/secrets.example.env](../config/secrets.example.env) |
| GitHub variables/secrets examples | [config/github-actions.variables.example.env](../config/github-actions.variables.example.env), [config/github-actions.secrets.example.env](../config/github-actions.secrets.example.env) |
| release env resolving | [scripts/release/resolve_release_env.py](../scripts/release/resolve_release_env.py) |
| publish asset rendering | [scripts/release/render_release_assets.py](../scripts/release/render_release_assets.py) |
| install/update/uninstall behavior | [scripts](../scripts) |
| runtime defaults in Python | [src/nagient/app/settings.py](../src/nagient/app/settings.py) |
| config builder and paths | [src/nagient/app/configuration.py](../src/nagient/app/configuration.py) |
| reconcile/status/preflight services | [src/nagient/application/services](../src/nagient/application/services) |
| transport plugin framework | [src/nagient/plugins](../src/nagient/plugins) |
| GitHub automation | [.github/workflows](../.github/workflows) |

## Как теперь выпускать релиз

Нормальный поток теперь такой:

1. Меняешь [src/nagient/version.py](../src/nagient/version.py), например на `0.2.0`.
2. Если менялся delivery contract, обновляешь код генерации manifests и tests.
3. Прогоняешь локально тесты и quality gates.
4. Пушишь в `main`.
5. `auto-tag.yml` создаёт `v0.2.0`, если такого тега ещё нет.
6. `auto-tag.yml` диспатчит `release.yml` для `v0.2.0`.
7. `release.yml` публикует артефакты и Docker image.
8. `update-center.yml` публикует Pages из ветки `main`.

Если тег `vX.Y.Z` уже существует, auto-tag его повторно не создаёт.
В таком случае новый `Release` run тоже не появится: это не ошибка, а защита от повторной публикации одной и той же версии.

Почему Pages не публикуется из `release.yml`:

- GitHub environment `github-pages` часто ограничен branch protection rules.
- Tag-based deploy вроде `v0.1.2` из-за этого может быть отклонён GitHub.
- Поэтому `release.yml` больше не пытается деплоить Pages, а `update-center.yml` остаётся единственным владельцем статического update center.

## Как настраивать домен для update center

Практический сценарий:

1. Открыть `Settings -> Pages`.
2. Выбрать deployment через GitHub Actions.
3. Вписать custom domain.
4. В `Actions -> Variables` добавить `UPDATE_BASE_URL` и `CUSTOM_DOMAIN`.
5. Настроить DNS.

### Если используется поддомен

Обычно достаточно:

- `CNAME` -> `<owner>.github.io`

Пример:

- `updates.your-domain.tld CNAME your-github-user.github.io`

### Если используется apex domain

GitHub Pages обычно требует `A`-записи:

- `185.199.108.153`
- `185.199.109.153`
- `185.199.110.153`
- `185.199.111.153`

И `AAAA`-записи:

- `2606:50c0:8000::153`
- `2606:50c0:8001::153`
- `2606:50c0:8002::153`
- `2606:50c0:8003::153`

Официальная документация GitHub Pages:

- https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/about-custom-domains-and-github-pages
- https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site

## Что делать дальше по коду

Следующий полезный слой разработки:

1. Реальный runtime loop вместо heartbeat-заглушки.
2. Provider abstraction для LLM.
3. Tool execution и permission model.
4. State/memory/storage contract.
5. HTTP/API или другой внешний surface.
6. Реальные миграции состояния.
7. Каналы уведомлений об обновлениях.

## Короткий checklist

- Не ломать manifests без синхронного апдейта scripts и tests.
- Не менять release flow без проверки `auto-tag.yml`, `release.yml` и `update-center.yml`.
- Не возвращать в код фейковые домены и жёстко прошитые repo placeholders.
- Если меняется версия, ориентироваться на auto-tag flow, а не на ручной git tag.
