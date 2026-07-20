# Руководство пользователя

Язык: [English](README.md) | Русский

Этот раздел предназначен для оператора, который устанавливает, настраивает,
обновляет и использует Nagient. Знания Python не нужны.

## С чего начать

- [Установка на Linux/macOS/Windows](../install.ru.md)
- [Запуск без Docker](../install.ru.md#runtime-без-docker)
- [Запуск через Docker Compose](../deploy.ru.md)
- [Поиск и установка плагинов](plugins.ru.md)
- [Секреты и переменные окружения](../env.ru.md)
- [Ежедневные CLI-команды](../commands.ru.md)
- [Диагностика запуска](../troubleshooting.ru.md)

## Варианты установки

| Установка | Установить плагин | Проверить |
| --- | --- | --- |
| Установщик на компьютере | `nagient plugin catalog list`, затем `nagient plugin catalog install <id>` | `nagient preflight` |
| Docker Compose | `docker compose exec nagient nagient plugin catalog list`, затем `docker compose exec nagient nagient plugin catalog install <id>` | `docker compose exec nagient nagient status` |
| Прямой Git-репозиторий | `nagient plugin install <url>#<tag>` | `nagient preflight` |

Проверенный каталог — безопасный вариант по умолчанию. `bundled` означает, что
расширение уже входит в поставку и его не нужно устанавливать.
