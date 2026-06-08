# Контракты плагинов

Расширения Nagient обнаруживаются как директории с manifest-файлами. Bundled-расширения
используют тот же путь discovery, что и пользовательские расширения.

## Транспортные плагины

Транспортный плагин содержит:

- `plugin.toml`
- entrypoint-файл из поля `entrypoint`
- `instructions.md`
- опциональный `schema.json`

Стабильные обязательные slots:

- `send_message`
- `send_notification`
- `normalize_inbound_event`
- `poll_inbound_events`
- `healthcheck`
- `selftest`
- `start`
- `stop`

Runtime всегда добавляет в outbound payload общие поля:

- `_transport_config`: конфиг профиля
- `_transport_id`: id transport instance
- `_transport_secrets`: secrets, найденные по config-полям, похожим на secret references

Плагин должен читать secrets из `_transport_secrets`, а не ждать специальных полей
конкретного транспорта.

Manifest транспорта может описать default target:

```toml
default_target_field = "chat_id"
default_target_config_key = "default_chat_id"
default_target_always_available = false
send_message_hint = "Опциональная подсказка для агента и CLI."
```

Так router может описывать кастомные транспорты без hardcode по plugin id.

## Tool plugins

Tool plugin содержит:

- `tool.toml`
- entrypoint-файл из поля `entrypoint`
- опциональный `schema.json`

Каждый `[[functions]]` entry описывает имя функции, binding, schemas, permissions,
side effect, approval policy и возможность автоодобрения ожидаемого действия:

```toml
[[functions]]
name = "vendor.deploy.run"
binding = "deploy"
description = "Deploy the selected target."
permissions = ["vendor.deploy"]
side_effect = "external"
approval_policy = "required"
auto_approve_when_expected = true
dry_run_supported = true
```

`auto_approve_when_expected` стоит включать только там, где явный запрос пользователя на
это конкретное действие достаточен, чтобы не спрашивать второй approval.

## Log channels

Transport, provider и tool manifests могут объявлять log channels:

```toml
[[log_channels]]
name = "transport.telegram"
description = "Telegram polling and outbound Bot API delivery."
default_level = "info"
```

Runtime config может переопределить уровни отдельных компонентов:

```toml
[agent.logging.components]
"transport.telegram" = "debug"
"tool.github.api" = "warning"
```

Если плагин не объявил log channels, платформа считает его молчащим по умолчанию, кроме
core runtime errors.
