# Плагины для пользователя

[English](plugins.md) · Русский · [Полное руководство по Plugin Hub](../plugins.ru.md)

## Личный компьютер

Откройте интерактивный установщик:

```bash
nagient plugin install
```

Или установите напрямую по verified ID или Git URL:

```bash
nagient plugin install nagient.telegram
nagient plugin install https://github.com/owner/nagient-plugin.git --ref v1.0.0
nagient preflight
nagient restart
```

## Docker Compose

```bash
docker compose exec nagient nagient plugin install
docker compose exec nagient nagient plugin install nagient.telegram
docker compose exec nagient nagient preflight
docker compose restart nagient
```

Плагин хранится в постоянных данных runtime, поэтому обычный restart его не удаляет. Для автоматического deployment используйте закреплённые репозитории в `NAGIENT_PLUGIN_SPECS`; подробности есть в [руководстве по серверу](../deploy.ru.md#5-установка-внешних-плагинов).

## Настройка

Установка и активация — разные шаги. Укажите ID плагина в профиле и включите его:

```env
NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=nagient.telegram
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN=123456:replace-me
```

Перед добавлением Telegram-бота в группы задайте ограничения:

```env
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_IDS=-1001234567890
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_CHAT_TYPES=supergroup
```

## Проверка и удаление

```bash
nagient plugin list
nagient plugin remove nagient.telegram
nagient preflight
```

В [полном руководстве по Plugin Hub](../plugins.ru.md) описаны статусы каталога, обновления, flags, доверие и правила Git sources.
