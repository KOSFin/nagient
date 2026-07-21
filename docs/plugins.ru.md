# Plugin Hub

[English](plugins.md) · Русский · [Содержание документации](README.ru.md)

Nagient хранит необязательные интеграции вне ядра. У каждого плагина свой репозиторий, манифест, версия, зависимости, документация и release cycle. Установленные плагины находятся в `~/.nagient` и не копируются в Python-пакет.

## Открыть установщик

```bash
nagient plugin install
```

В интерактивном терминале Plugin Hub показывает все проверенные внешние плагины, их тип и статус `installed` или `available`. Можно выбрать плагин из списка или пункт установки по Git URL. В неинтерактивном shell эта же команда печатает проверенный каталог и готовые команды, не ожидая ввода.

## Установить напрямую

Короткий проверенный ID — самый простой воспроизводимый источник:

```bash
nagient plugin install nagient.telegram
nagient plugin install nagient.github_api
```

Nagient берёт проверенный репозиторий и закреплённый релиз из каталога. Совместимый Git-репозиторий можно установить обычной ссылкой без префикса:

```bash
nagient plugin install https://github.com/owner/nagient-plugin.git
nagient plugin install https://github.com/owner/nagient-plugin.git --ref v1.2.0
```

`--force` переустанавливает плагин, `--no-dependencies` пропускает создание изолированного окружения, а `--format json` предназначен для автоматизации.

## Проверенный каталог

| Плагин | Семейство | Статус | Установка |
| --- | --- | --- | --- |
| [Console Transport](commands.ru.md#21-базовые) | Transport | Встроен | Не требуется |
| [Webhook Transport](plugin-contracts.ru.md) | Transport | Встроен | Не требуется |
| [Telegram Transport](https://github.com/KOSFin/nagient-transport-telegram) | Transport | Проверенный внешний | `nagient plugin install nagient.telegram` |
| [GitHub API Tool](https://github.com/KOSFin/nagient-tool-github-api) | Tool | Проверенный внешний | `nagient plugin install nagient.github_api` |

Полный каталог и фильтр по семейству:

```bash
nagient plugin catalog list
nagient plugin catalog list --family transport
nagient plugin catalog list --format json
```

## Настроить установленный плагин

Установка делает плагин доступным для discovery, а конфигурация включает конкретный профиль. Все поля объявлены в манифесте. Env overrides используют одну форму:

```text
NAGIENT_<FAMILY>__<PROFILE_ID>__<FIELD>=value
```

Пример Telegram:

```env
NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=nagient.telegram
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
TELEGRAM_BOT_TOKEN=123456:replace-me
```

Пример GitHub API:

```env
NAGIENT_TOOL__GITHUB_API__PLUGIN=nagient.github_api
NAGIENT_TOOL__GITHUB_API__ENABLED=true
NAGIENT_TOOL__GITHUB_API__TOKEN_SECRET=GITHUB_TOKEN
GITHUB_TOKEN=github_pat_replace_me
```

Секретное поле содержит имя секрета. Само значение храните в environment, `secrets.env`, `tool-secrets.env` или соответствующем JSON override.

## Docker Compose

Используйте тот же Plugin Hub внутри постоянного контейнера:

```bash
docker compose exec nagient nagient plugin install
docker compose exec nagient nagient plugin install nagient.telegram
docker compose exec nagient nagient preflight
docker compose restart nagient
```

Для автоматической установки при первом запуске закрепите источники в `.env`:

```env
NAGIENT_PLUGIN_SPECS=https://github.com/KOSFin/nagient-transport-telegram.git#v0.2.0,https://github.com/KOSFin/nagient-tool-github-api.git#v0.2.0
```

Установленные плагины сохраняются в постоянном mount `./data` после перезапуска контейнера.

## Проверка, обновление и удаление

```bash
nagient plugin list
nagient plugin install nagient.telegram --force
nagient plugin remove nagient.telegram
nagient preflight
```

Переустановка по verified ID использует ref, закреплённый в текущем каталоге. Для произвольного репозитория передайте нужный `--ref` явно.

## Модель доверия

`verified` означает, что каталог Nagient закрепляет проверенные source и ref. Это не sandbox для произвольного кода. Перед установкой непроверенного URL изучите манифест, исходный код, зависимости, разрешения и сетевое поведение. Оставляйте workspace в режиме `bounded`, если конкретному workflow не нужен более широкий доступ.

Авторам плагинов стоит начать с [официального шаблона](https://github.com/KOSFin/nagient-plugin-template), а затем открыть статью [Создание первого плагина](PLUGIN_DEVELOPMENT.ru.md).
