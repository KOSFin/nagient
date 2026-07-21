# Руководство разработчика

[English](README.md) · Русский · [Вся документация](../README.ru.md)

Nagient поддерживает два runtime расширений: Python-плагины предоставляют `build_plugin()`, а process-плагины обмениваются одной JSON-парой через stdin/stdout. Оба варианта используют общие манифесты и discovery-модель.

## Выберите направление

| Задача | С чего начать |
| --- | --- |
| Создать новый плагин | [Руководство по разработке плагинов](../PLUGIN_DEVELOPMENT.ru.md) |
| Начать с чистого репозитория | [Официальный шаблон плагина](https://github.com/KOSFin/nagient-plugin-template) |
| Реализовать runtime adapter | [Контракты плагинов](../plugin-contracts.ru.md) |
| Разобраться в ownership и discovery | [Архитектура](../architecture.ru.md) |
| Подготовить contribution | [Тестирование и CI](testing.ru.md) |

## Содержание для разработчика

| Статья | Что внутри |
| --- | --- |
| [Создание первого плагина](../PLUGIN_DEVELOPMENT.ru.md) | Структура репозитория, манифесты, поля, зависимости, проверка и публикация. |
| [Контракты плагинов](../plugin-contracts.ru.md) | Протоколы transport, provider, tool, Python и process runtime. |
| [Архитектура](../architecture.ru.md) | Границы ядра, зависимости, runtime flow, безопасность и state. |
| [Тестирование и CI](testing.ru.md) | Unit, integration, smoke, lint и release checks. |
| [Как внести вклад](../../CONTRIBUTING.md) | Локальная настройка, code style, commits и pull requests. |

Сетевые SDK и нативные зависимости должны находиться в репозитории плагина. В ядре остаются только console, webhook, providers и системные tools, необходимые для полезного первого запуска.
