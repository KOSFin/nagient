# Руководство пользователя

[English](README.md) · Русский · [Вся документация](../README.ru.md)

Этот раздел предназначен для эксплуатации Nagient. Знания Python не нужны.

## Рекомендуемый маршрут

1. [Установите Nagient](../install.ru.md).
2. Запустите `nagient setup` и [настройте provider и секреты](../configuration.ru.md).
3. Откройте диалог командой `nagient chat`.
4. [Установите нужные transports и tools](plugins.ru.md).
5. Выполните `nagient preflight`, затем `nagient up` и `nagient status`.

## Содержание руководства

| Статья | Когда она нужна |
| --- | --- |
| [Установка и обновления](../install.ru.md) | Установка, обновление или удаление Nagient на компьютере. |
| [Развёртывание на сервере](../deploy.ru.md) | Эксплуатация Nagient через Docker Compose. |
| [Команды и ежедневная работа](../commands.ru.md) | CLI, chat, status, logs и lifecycle-команды. |
| [Конфигурация и секреты](../configuration.ru.md) | Выбор providers, tools, workspace и хранилища секретов. |
| [Работа с плагинами](plugins.ru.md) | Подключение Telegram, GitHub API и других внешних расширений. |
| [Переменные окружения](../env.ru.md) | Настройка Compose или автоматизации без интерактивного setup. |
| [Диагностика проблем](../troubleshooting.ru.md) | Ошибка preflight, запуска, Docker, provider или активации плагина. |

## Установка плагинов

| Runtime | Открыть Plugin Hub | Проверить |
| --- | --- | --- |
| Личный компьютер | `nagient plugin install` | `nagient preflight` |
| Docker Compose | `docker compose exec nagient nagient plugin install` | `docker compose exec nagient nagient preflight` |
| Автоматизация | `nagient plugin install <verified-id-or-git-url>` | `nagient plugin list` |
