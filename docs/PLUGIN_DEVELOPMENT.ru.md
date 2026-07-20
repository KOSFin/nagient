# Разработка плагинов

Язык: [English](PLUGIN_DEVELOPMENT.md) | Русский

## Репозиторий-шаблон

Поддерживаемый стартовый репозиторий называется `nagient-plugin-template`. В нём
есть минимальный transport-манифест, реализация Python, контрактные тесты и CI
для Python 3.11/3.12. Для нового расширения форкните этот репозиторий; не копируйте
production-реализацию Telegram или GitHub и не удаляйте файлы наугад. До отдельной
публикации тот же шаблон доступен рядом с основным checkout в рабочей папке.

## Как устроен плагин

Плагин — это отдельный Git-репозиторий с одним манифестом и entrypoint-файлом.
Nagient не требует ручной регистрации: после установки он находит манифест,
проверяет его и загружает `build_plugin()`.

Поддерживаются три семейства:

| Семейство | Манифест | Каталог в runtime |
| --- | --- | --- |
| transport | `plugin.toml` | `@plugins` |
| provider | `provider.toml` | `@providers` |
| tool | `tool.toml` | `@tools` |

В репозитории должен быть ровно один такой манифест. Для Python-плагина
`entrypoint` должен экспортировать `build_plugin()`. Для изолированного
процесса укажите `runtime = "process"` и команду в манифесте.

## Зависимости плагина

Зависимости не устанавливаются в основное окружение Nagient. Это важно: один
плагин не может случайно сломать версии библиотек другого плагина или самого
агента. Укажите их в манифесте:

```toml
runtime = "python"
dependencies = ["aiogram>=3,<4", "aiohttp>=3.9"]
# Необязательно: дополнительные зависимости из файла репозитория
requirements_file = "requirements.txt"
```

Команда установки сама создаёт `<каталог-плагина>/.venv` и ставит туда эти
пакеты:

```bash
nagient plugin install transport:https://github.com/owner/telegram-aiogram.git#v1.0.0
nagient plugin list --format json
```

В Docker `.venv` хранится вместе с установленным плагином в подключённом
каталоге `data`, поэтому перезапуск контейнера не ставит зависимости заново.
При ручном обновлении используйте `--upgrade-dependencies`. Флаг
`--no-dependencies` предназначен только для офлайн-подготовки файлов и обычно
не нужен.

Для process-плагина Python entrypoint запускается тем же `.venv`, поэтому
`aiogram`, `aiohttp` и другие библиотеки доступны без изменения окружения
Nagient. Такой режим предпочтителен для долгоживущих async-клиентов.

### Готовый пример aiogram

В репозитории есть reference-плагин `examples/plugins/telegram-aiogram`.
Скопируйте эту директорию в отдельный Git-репозиторий, опубликуйте его и
установите по URL. Затем включите его как обычный transport с
`bot_token_secret` и при необходимости `proxy_url`.

## Установка

```bash
nagient plugin install provider:https://github.com/owner/nagient-provider.git#v1.0.0
nagient plugin list
nagient plugins --all
nagient plugin remove owner.provider
```

Префикс `provider:`, `transport:` или `tool:` нужен, если репозиторий содержит
несколько типов манифестов. Суффикс `#v1.0.0` фиксирует tag или commit и
рекомендуется для production.

В Compose используйте `NAGIENT_PLUGIN_SPECS`:

```dotenv
NAGIENT_PLUGIN_SPECS=provider:https://github.com/owner/provider.git#v1.0.0,tool:https://github.com/owner/tool.git#8f31abc
```

При первом запуске репозитории устанавливаются в `data`, а обработанные строки
сохраняются в `data/state/installed-plugin-specs`. Это делает перезапуски
идемпотентными.

## Переменные плагина

Поля из `config_fields` получают значения по общему шаблону:

```dotenv
NAGIENT_PROVIDER__MY_PROVIDER__BASE_URL=https://api.example.com
NAGIENT_PROVIDER__MY_PROVIDER__API_KEY_SECRET=MY_PROVIDER_API_KEY
MY_PROVIDER_API_KEY=секрет
```

Для transport используется `NAGIENT_TRANSPORT__ID__FIELD`, для tool —
`NAGIENT_TOOL__ID__FIELD`. Секреты не встраивайте в код и не кладите в Git:
плагин должен объявлять ссылку на имя секрета, а значение передаётся через
`.env`, `secrets.env` или `NAGIENT_SECRETS_JSON`.

## Размещение вручную

При ручной установке файлы должны лежать так:

```text
~/.nagient/
├── plugins/<id>/plugin.toml
├── providers/<id>/provider.toml
└── tools/<id>/tool.toml
```

Пути можно проверить командой `nagient paths`. После изменения файлов выполните
`nagient preflight` или перезапустите контейнер.

## Безопасность и тестирование

- загружайте только доверенные репозитории;
- фиксируйте tag или commit;
- ограничивайте workspace через `NAGIENT_SAFE_MODE=true`;
- добавьте в репозиторий тесты манифеста и `build_plugin()`;
- перед включением запускайте `nagient preflight`.

Полный формат полей и runtime-контрактов: [plugin-contracts.ru.md](plugin-contracts.ru.md).
