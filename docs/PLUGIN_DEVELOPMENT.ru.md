# Разработка плагинов

Язык: [English](PLUGIN_DEVELOPMENT.md) | Русский

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
