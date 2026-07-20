# Пользователь: плагины

Язык: [English](plugins.md) | Русский

## 1. Найти плагин

```bash
nagient plugin catalog list
nagient plugin catalog list --family transport
```

Короткий текстовый вывод рассчитан на один экран терминала. Для автоматизации
используйте `--format json`. Команда `nagient plugin list` показывает только
внешние репозитории, установленные в runtime.

## 2. Установка на компьютере

```bash
nagient plugin catalog install <plugin-id>
nagient preflight
nagient reconcile
```

После изменения конфигурации перезапустите runtime:

```bash
nagient restart
```

## 3. Установка через Docker Compose

Команды выполняются внутри постоянного контейнера. Плагин хранится в `./data` и
переживает перезапуск:

```bash
docker compose exec nagient nagient plugin catalog list
docker compose exec nagient nagient plugin catalog install <plugin-id>
docker compose exec nagient nagient preflight
docker compose restart nagient
```

Для автоматического развёртывания укажите закреплённый Git-источник в
`NAGIENT_PLUGIN_SPECS` файла `.env` и выполните `docker compose up -d`. Используйте
тег или commit, а не плавающую ветку.

Примеры официальных плагинов:

```bash
docker compose exec nagient nagient plugin catalog install nagient.telegram
docker compose exec nagient nagient plugin catalog install nagient.github_api
```

## 4. Настроить плагин

Поля берутся из JSON каталога или манифеста. Универсальная форма env:

```text
NAGIENT_<FAMILY>__<PLUGIN_ID>__<FIELD>=value
```

Секретные поля содержат имя секрета. Не помещайте токен непосредственно в
публичный Compose-файл.

## 5. Безопасность Telegram

Telegram уже входит в поставку. До включения группового бота ограничьте его:

```env
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS=-1001234567890
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=supergroup
```
