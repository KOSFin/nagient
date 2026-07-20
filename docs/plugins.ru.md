# Плагины

Язык: [English](plugins.md) | Русский

Nagient отделяет runtime от расширений. Плагин — это репозиторий с манифестом
(`plugin.toml`, `provider.toml` или `tool.toml`), инструкциями и, при необходимости,
изолированными зависимостями. Установленные плагины находятся в `~/.nagient` и
не попадают в пакет ядра.

## Каталог и установка

```bash
nagient plugin catalog list
nagient plugin catalog list --family transport
nagient plugin list
```

Записи `bundled` уже входят в Nagient. Внешний проверенный плагин можно поставить
по его ID, не разыскивая репозиторий вручную:

```bash
nagient plugin catalog install <plugin-id>
nagient preflight
nagient status
```

`--format json` предназначен для скриптов. Прямую установку Git-репозитория тоже
можно использовать, но она не считается проверенной:

```bash
nagient plugin install transport:https://github.com/ORG/REPO.git#v1.0.0
```

Официальные отдельные репозитории:

| Плагин | Установка |
| --- | --- |
| `nagient.telegram` | `nagient plugin catalog install nagient.telegram` |
| `nagient.github_api` | `nagient plugin catalog install nagient.github_api` |

## Telegram

Telegram входит в поставку и включается настройкой. Токен задаётся только через
имя секрета:

```env
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN=123456:replace-me
```

Ограничения групп и пользователей включаются списками. Если список непустой,
события вне списка отбрасываются до передачи агенту:

```env
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS=-1001234567890,123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=private,supergroup
```

Транспорт предоставляет `telegram.streamMessage`: runtime может отправить части
накопленные части ответа и постепенно редактировать одно сообщение, группируя обновления с учётом
лимитов Telegram.

## Поля плагина и env

Каждый плагин объявляет собственные поля в манифесте. Имя env строится одинаково:

```text
NAGIENT_<FAMILY>__<PLUGIN_ID>__<FIELD>=value
```

Например, `allowed_chat_ids` превращается в
`NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS`. Секретное поле содержит имя
секрета, а его значение хранится в окружении или `NAGIENT_SECRETS_JSON`.

## Доверие и обновления

Перед установкой непроверенного плагина проверьте `plugin.toml`, URL и закреплённый
`#ref`. После установки запускайте `nagient preflight`; рабочий каталог оставляйте
в режиме `bounded`, если расширенный доступ не нужен конкретному workflow.
