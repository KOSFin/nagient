# Архитектурные заметки

Язык: [English](architecture.md) | Русский

Nagient разделён на узкую control-surface часть и централизованную release/update модель.

## Переносимость и зависимости

Ядро намеренно использует стандартную библиотеку Python для CLI, конфигурации,
HTTP, process-adapter и хранения состояния. Так wheel остаётся небольшим, а
установщики работают на Python 3.11 и 3.12 без нативного toolchain. Необязательные
интеграции находятся в плагинах: их зависимости ставятся в `<plugin>/.venv` и не
заставляют каждый runtime скачивать Telegram-, cloud- или database-стек. Зависимость
переезжает в ядро только при необходимости для activation path и доказанной
кроссплатформенной пользе.

## Слои

- `nagient.app` связывает settings и сервисы.
- `nagient.application.services` содержит use-case логику, например health-check и поиск обновлений.
- `nagient.domain` владеет release-сущностями и сравнением семантических версий.
- `nagient.infrastructure` отвечает за manifests, registry loading, runtime heartbeat и файловый transport.
- `nagient.tools` содержит tool plugin framework и built-in tools для workspace, backup, interaction и reconcile.
- `nagient.workspace` отвечает за bounded/unsafe workspace policy, `.nagient/` layout и job persistence.
- `nagient.security` отвечает за secret broker и file-backed secure interaction / approval workflows.
- `nagient.migrations` строит упорядоченный план upgrade-шагов из release metadata.

## Bootstrap и activation cycle

Активация runtime теперь проходит через единый pipeline независимо от того, запустил ли пользователь систему через локальный CLI, `curl | sh`, PowerShell, Docker image или Docker Compose:

1. Сборка конфига из `config.toml`, env defaults и `secrets.env`.
2. Discovery built-in и пользовательских provider, transport и tool plugins из `@providers`, `@plugins` и `@tools`.
3. Прогон `preflight`: lint конфига, проверка secret refs, self-tests плагинов и transport health checks.
4. Прогон `reconcile` с сохранением `activation-report.json`, `effective-config.json` и `last-known-good.json`, а также с созданием видимой `.nagient/` layout-модели workspace.
5. Старт runtime loop только если activation report разрешён safe mode.

Safe mode включён по умолчанию. Если его выключить, runtime может стартовать в `degraded` состоянии.

## Runtime-контракт плагинов

## Bundled и внешние плагины

В wheel встроены только console и webhook transport, необходимые для первого
offline-запуска. Необязательные интеграции находятся в отдельных репозиториях и
устанавливаются в runtime home. Telegram и GitHub API — проверенные внешние
плагины; их зависимости и релизы намеренно отделены от ядра.

Пользовательские provider, transport и tool plugins могут работать как Python-модули или как внешние процессы на любом языке.

- Python plugins используют `runtime = "python"` и экспортируют `build_plugin()` из указанного entrypoint.
- Process plugins используют `runtime = "process"` и запускают настроенный `command` или `entrypoint`.
- Process-вызов читает один JSON request из stdin и пишет один JSON response в stdout.
- Request содержит `protocol = "nagient.process.v1"` и `method`, например `execute`, `send_message`, `list_models` или `generate_assistant_response`.
- Успешный ответ: `{ "status": "success", "output": ... }`; ошибка: `{ "status": "error", "message": "..." }`.

## Контракт transport plugin

Transport plugin объявляет:

- `plugin.toml` для manifest metadata и function bindings
- entrypoint вроде `transport.py`, `transport.sh` или свой command
- `instructions.md` с агентной инструкцией по использованию транспорта
- optional `schema.json` для plugin-local config schema

Каждый transport plugin обязан декларировать slot bindings для:

- `send_message`
- `send_notification`
- `normalize_inbound_event`
- `poll_inbound_events`
- `healthcheck`
- `selftest`
- `start`
- `stop`

Также plugin может объявлять custom namespaced функции вроде `telegram.showPopup` или `webhook.replyJson`.
Interaction capabilities и mappings позволяют core выбрать inline approval, typing,
live draft, реакцию или текстовый fallback без hardcode transport ID.

Runtime работает с transport plugin через единый контракт:

1. `poll_inbound_events` возвращает новые сырые transport-события или вычитывает их из внутренней очереди.
2. `normalize_inbound_event` переводит каждое сырое событие в transport-agnostic payload.
3. Нормализованный payload по возможности должен содержать `event_type`, `session_id`, `text`
   и `reply_target`, если транспорт поддерживает ответ.
4. Runtime получает ответ от выбранного provider и передает
   `{**reply_target, "text": "<reply>"}` обратно в `send_message`.

Транспорт с progressive delivery объявляет `stream.draft` или другую capability-функцию.
Runtime передаёт снимки прогресса, а transport отвечает за API, лимиты, batching и
финальное durable сообщение.

## Agent Runtime Core

Теперь у Nagient есть структурированный turn contract, а не только heartbeat-заглушка:

- `AgentTurnRequest`
- `AgentTurnContext`
- `AssistantResponse`
- `NormalizedToolCall`
- `ToolExecutionRequest`
- `ToolExecutionResult`
- `InteractionRequest`
- `ApprovalRequest`
- `AgentTurnResult`

Этот слой намеренно узкий: основной пользовательский ответ отделён от tool calls, approvals, secure interactions и config mutation intents.

## Workspace И Security

- В активном workspace создаётся видимая `.nagient/` папка с `memory/`, `notes/`, `plans/`, `jobs/` и `scripts/`.
- Чувствительное состояние остаётся вне workspace, в Nagient home/state директориях.
- `secrets.env` остаётся core secret store для transport/provider уровня.
- `tool-secrets.env` используется как отдельный secret store для tool/connector уровня.
- Secret broker отдаёт агентному слою только metadata; raw значения резолвятся только при исполнении и редактируются в outputs.
- High-risk действия вроде restore flows и destructive tool operations проходят через approval requests вместо прямого исполнения.
- Approval привязан к исходным transport session и sender. После approval агент
  продолжает свой цикл с результатом tool action и может выполнить зависимые calls.

## Панель оператора

Compose ENV остаётся bootstrap и secret lock-слоем, а профили хранятся в `config.toml`.
Необязательная password-protected localhost-панель показывает preview и записывает
persisted конфигурацию без raw secrets. Порт публикуется только через overlay
`docker-compose.control-panel.yml`.

## Контракт update center

У update center два основных JSON-документа:

1. `channels/<channel>.json` указывает на актуальный release manifest канала.
2. `manifests/<version>.json` описывает Docker image, установщики, deployment assets, миграции и release notices.

Именно этот контракт должны одинаково читать shell-установщики, PowerShell-установщики, CLI и будущие каналы уведомлений.

## Модель поставки

Тег `vX.Y.Z` должен порождать:

1. Python-дистрибутив в `dist/`.
2. Docker image `docker.io/<namespace>/<image>:X.Y.Z`.
3. Versioned installer assets по адресу `<update-base-url>/X.Y.Z/`.
4. Release manifest по адресу `<update-base-url>/manifests/X.Y.Z.json`.
5. Указатель канала по адресу `<update-base-url>/channels/stable.json`.
