# Архитектурные заметки

Язык: [English](architecture.md) | Русский

Nagient разделён на узкую control-surface часть и централизованную release/update модель.

## Слои

- `nagient.app` связывает settings и сервисы.
- `nagient.application.services` содержит use-case логику, например health-check и поиск обновлений.
- `nagient.domain` владеет release-сущностями и сравнением семантических версий.
- `nagient.infrastructure` отвечает за manifests, registry loading, runtime heartbeat и файловый transport.
- `nagient.tools` содержит tool plugin framework и built-in tools для workspace, backup, interaction, reconcile и GitHub.
- `nagient.workspace` отвечает за bounded/unsafe workspace policy, `.nagient/` layout и job persistence.
- `nagient.security` отвечает за secret broker и file-backed secure interaction / approval workflows.
- `nagient.migrations` строит упорядоченный план upgrade-шагов из release metadata.

## Bootstrap и activation cycle

Активация runtime теперь проходит через единый pipeline независимо от того, запустил ли пользователь систему через локальный CLI, `curl | sh`, PowerShell, Docker image или Docker Compose:

1. Сборка конфига из `config.toml`, env defaults и `secrets.env`.
2. Discovery built-in и пользовательских Python transport plugins из `plugins/`.
3. Прогон `preflight`: lint конфига, проверка secret refs, self-tests плагинов и transport health checks.
4. Прогон `reconcile` с сохранением `activation-report.json`, `effective-config.json` и `last-known-good.json`, а также с созданием видимой `.nagient/` layout-модели workspace.
5. Старт runtime loop только если activation report разрешён safe mode.

Safe mode включён по умолчанию. Если его выключить, runtime может стартовать в `degraded` состоянии.

## Контракт transport plugin

Transport plugin теперь это Python-компонент с:

- `plugin.toml` для manifest metadata и function bindings
- `transport.py` с реализацией
- `instructions.md` с агентной инструкцией по использованию транспорта
- optional `schema.json` для plugin-local config schema

Каждый transport plugin обязан декларировать slot bindings для:

- `send_message`
- `send_notification`
- `normalize_inbound_event`
- `healthcheck`
- `selftest`
- `start`
- `stop`

Также plugin может объявлять custom namespaced функции вроде `telegram.showPopup` или `webhook.replyJson`.

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
