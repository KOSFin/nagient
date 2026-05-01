# План развития agent runtime, памяти и transport layer

Этот документ фиксирует текущее состояние проекта и целевую архитектуру для следующего большого этапа: полноценный агентный runtime с памятью, transport-aware workflow, multi-transport outbound, системным промптом, scheduler/jobs и расширенным Telegram transport.

## 1. Что уже есть

- Есть базовый контракт transport plugin с обязательными runtime-слотами: `send_message`, `send_notification`, `normalize_inbound_event`, `poll_inbound_events`, `healthcheck`, `self_test`, `start`, `stop`.
- Есть transport registry, manager и scaffold для built-in и кастомных transport plugins.
- Есть built-in транспорты `console`, `webhook`, `telegram`.
- Есть provider layer с `generate_message(...)`, но он пока ориентирован на простой chat flow, а не на агентный turn loop с tool calls.
- Есть tool plugin framework, встроенные workspace/system tools, approval/interaction workflow, backup checkpoints, secret broker и workspace manager.
- Есть visible workspace layout: `.nagient/memory`, `.nagient/notes`, `.nagient/plans`, `.nagient/jobs`, `.nagient/scripts`.
- Есть `JobStore`, но scheduler как рабочий runtime-компонент пока отсутствует.

## 2. Главные разрывы между текущим кодом и целевой системой

### 2.1 Agent runtime пока не агентный

Сейчас inbound transport event в runtime приводит к очень простому сценарию:

1. transport poller получает событие
2. событие нормализуется
3. runtime достает `text`
4. вызывается `provider_service.chat(...)`
5. текст ответа отправляется обратно через transport

Это хороший каркас для живого polling транспорта, но этого недостаточно для:

- tool execution loop
- системного промпта
- долговременного session context
- памяти и retrieval
- approvals/interactions прямо внутри диалога
- multi-transport routing
- self-wake и jobs

### 2.2 Transport contract смешивает runtime-обязанности и agent-facing функции

Плагин обязан уметь `poll/start/stop`, но это не те функции, которые нужно напрямую показывать модели. Нужны два разных уровня:

- `runtime transport contract`: polling, normalization, lifecycle, health
- `agent-facing transport operations`: отправка сообщения, typing, reaction, callback answer, outbound routing

Сейчас второй уровень не стандартизирован.

### 2.3 Память как директории уже есть, но реальной memory system нет

Папки `.nagient/memory` и `.nagient/notes` создаются, но:

- нет transcript storage
- нет search/retrieval
- нет summary/pruning
- нет отличия между “памятью контекста” и “заметками агента”
- нет лимитов на историю по сообщениям или по токенам

### 2.4 Workflow слой уже хороший, но transport-aware UX еще не доведен

Есть:

- `InteractionRequest`
- `ApprovalRequest`
- post-submit actions
- secret redaction

Но пока подтверждения и secure input по сути завершаются через отдельные CLI-команды, а не через живой transport session.

### 2.5 Telegram transport уже рабочий, но еще слишком узкий

Сейчас в built-in Telegram transport уже есть:

- long polling
- `sendMessage`
- callback answer
- popup alert
- reply_target normalization
- offset persistence

Но пока нет:

- typing/presence
- edit/delete
- reactions
- richer outbound functions
- transport-rendered approvals/interactions
- отдельного outbound API для отправки сообщения в Telegram из console/другого транспорта

## 3. Целевая архитектура

## 3.1 Разделить систему на 4 явных слоя

### A. Transport runtime layer

Это низкоуровневый слой доставки событий и отправки ответов.

Обязанности:

- polling / webhook intake / session binding
- normalize inbound event
- lifecycle `start/stop`
- health/self-test
- transport-specific persistence

### B. Agent execution layer

Это новый основной runtime-сервис.

Обязанности:

- загрузка системного промпта
- сбор tool catalog
- сбор контекста сессии
- вызов provider в режиме structured turn
- исполнение tool calls
- повторные шаги после tool results
- сохранение transcript и summaries
- финальная отправка ответа в выбранный transport

### C. Memory/session layer

Отдельный сервис, который отвечает за:

- transcript storage
- summaries
- “focus window”
- retrieval по старым сообщениям
- заметки агента
- pinned facts / plans / references

### D. Workflow/scheduler layer

Отдельный слой для:

- approvals
- secure inputs
- jobs
- delayed wakeups
- recurring tasks

## 3.2 Agent runtime должен работать через новый provider contract

Нужен новый provider method, например:

- `generate_assistant_response(...) -> AssistantResponse`

или

- `run_agent_turn(...) -> AssistantResponse`

Почему это обязательно:

- текущий `generate_message(...)` возвращает только строку
- `AgentTurnService` уже умеет принять `AssistantResponse`, но сам provider его не формирует
- без structured provider output невозможно нормально встроить tools, approvals, memory intents и transport routing

Старый `generate_message(...)` нужно оставить для `nagient chat`.

## 3.3 Memory system: рекомендую SQLite + файловые заметки

### Почему не только файлы

Если хранить transcript и память только в файлах:

- будет медленный поиск
- будет сложнее делать retrieval по ключевым словам
- тяжелее хранить флаги `in_focus`, summaries, session metadata

### Почему не только БД

Если хранить заметки только в БД:

- пользователю неудобно их читать и править руками
- теряется прозрачность
- хуже интеграция с workspace и git

### Практичное решение

- transcript и machine memory хранить в SQLite
- human-readable заметки и планы хранить файлами в workspace
- файлы индексировать в SQLite

### Где хранить

- visible workspace:
  - `.nagient/notes/*.md`
  - `.nagient/plans/*.md`
  - `.nagient/jobs/*.json`
  - при желании `.nagient/memory/*.md` только для несекретных summaries
- private runtime state:
  - `state/workspaces/<workspace_id>/agent-state.sqlite3`

Так безопаснее, потому что в transcript могут попадать чувствительные куски пользовательского диалога.

### Что хранить в SQLite

- `sessions`
- `messages`
- `memory_items`
- `note_index`
- `summaries`
- `focus_state`

### Минимальные поля

- `messages`: `message_id`, `session_id`, `transport_id`, `role`, `content`, `created_at`, `tokens_estimate`, `in_focus`, `summary_id`, `metadata_json`
- `memory_items`: `memory_id`, `workspace_id`, `session_id`, `kind`, `title`, `content`, `keywords`, `source`, `pinned`, `created_at`
- `note_index`: `note_id`, `path`, `title`, `content`, `keywords`, `updated_at`

### Поиск

Лучший первый шаг без новых зависимостей:

- SQLite FTS5, если доступен
- fallback на `LIKE` + keywords

Это дает быстрый и простой поиск без внедрения внешней vector DB на первом этапе.

## 3.4 Лимиты памяти: нужен и жесткий, и динамический

Рекомендую реализовать оба режима, как ты и описал.

### Жесткий лимит

- хранится в конфиге
- например `hard_message_limit = 100`
- при превышении старые сообщения не удаляются из БД, а выводятся из active prompt window
- если нужно, из них автоматически строится summary

Важно: удалять нужно не из хранилища, а из “активного prompt context”. Иначе модель потеряет возможность retrieval.

### Динамический лимит

- флаг `dynamic_focus_enabled = true|false`
- число вроде `dynamic_focus_messages = 10`
- это не физический лимит хранения, а лимит активной фокусной зоны

### Как это должно работать

В каждом turn context собирается:

1. системный промпт
2. transport instructions
3. pinned memory
4. summary текущей сессии
5. последние `N` сообщений
6. focus subset последних `K` сообщений
7. retrieval results по запросу или по auto-trigger

### Кто должен управлять focus

Не стоит давать модели “молча” самой решать это чисто текстом. Лучше так:

- система по умолчанию держит последние `K` сообщений в focus
- модель может вызвать tool вроде `memory.set_focus(...)`
- система может авто-подтягивать retrieval, если видит фразы вроде “вспомни”, “ты писал”, “ранее мы обсуждали”

Это предсказуемее и тестируемее.

## 3.5 Заметки агента: рекомендую оставить папку и добавить индекс

Папка `.nagient/notes/` уже правильная идея.

Лучший формат:

- markdown файлы для человеческой читаемости
- отдельный индекс в SQLite для поиска по содержимому

Нужны built-in tools:

- `memory.notes.create`
- `memory.notes.update`
- `memory.notes.search`
- `memory.notes.delete`
- `memory.notes.list`

Отдельно нужны memory tools для transcript/pinned facts:

- `memory.search_messages`
- `memory.search_memory`
- `memory.pin_fact`
- `memory.unpin_fact`
- `memory.get_session_summary`
- `memory.set_focus`

## 3.6 System prompt должен стать частью конфигурации

Сейчас системный промпт есть только как ручной `--system` для `nagient chat`.

Нужно добавить в конфиг:

```toml
[agent]
default_provider = "openai"
require_provider = true
system_prompt_file = "~/.nagient/prompts/system.md"

[agent.memory]
hard_message_limit = 100
dynamic_focus_enabled = true
dynamic_focus_messages = 10
summary_trigger_messages = 20
retrieval_max_results = 8
```

Также стоит добавить CLI:

- `nagient setup agent`
- `nagient prompt show`
- `nagient prompt path`

Почему файл, а не только inline string:

- удобнее редактировать
- удобно версионировать
- проще показывать пользователю

## 3.7 Transport plugins: рекомендую ввести capability model

Обязательный runtime-контракт можно оставить почти как есть.

Но нужно ввести еще стандартизированные optional capabilities:

- `typing`
- `edit_message`
- `delete_message`
- `reaction`
- `callback_answer`
- `approval_render`
- `interaction_render`
- `outbound_targeting`

### Важно

`poll/start/stop` обязательны для plugin runtime, но не должны торчать в tool surface модели.

### Что модель должна видеть

Нужен adapter, который строит agent-facing transport tools поверх transport plugins:

- `transport.send_message`
- `transport.send_notification`
- `transport.list_targets`
- `transport.send_typing`
- `transport.set_reaction`
- `transport.answer_callback`

и transport-specific wrappers, если capability присутствует.

Этот adapter должен сам:

- находить transport instance
- подмешивать transport config
- подмешивать нужные secret-backed runtime параметры
- не раскрывать модели `_token` и подобные внутренние поля

## 3.8 Multi-transport outbound

Чтобы агент из console мог отправить сообщение в Telegram, нужен транспортный router.

### Предлагаю так

- в runtime появляется `TransportRouterService`
- agent-facing tool вызывает router, а не plugin напрямую
- router умеет:
  - отправить ответ в текущий transport
  - отправить outbound в другой transport instance
  - использовать explicit target payload

Пример:

- пользователь пишет в console: “отправь мне сообщение в telegram”
- модель вызывает `transport.send_message`
- указывает `transport_id = "telegram"` и `chat_id`
- router сам вызывает Telegram plugin и приклеивает runtime credentials

## 3.9 Workflow должен стать transport-aware по-настоящему

Текущий `WorkflowService` уже хороший фундамент: он умеет сохранять approval/interaction и выполнять post-submit actions.

Что нужно добавить:

- pending workflow matcher на входящих transport событиях
- transport-rendered approve/reject/cancel actions
- secure reply binding к конкретной session/message/request

### Telegram UX

- approval request можно рендерить inline keyboard
- callback data содержит `pending_action_id`
- callback query идет не к модели, а сначала в workflow resolver

### Console UX

- остается текстовый fallback
- пользователь может ответить отдельной CLI-командой или текстом в интерактивной сессии

## 3.10 Scheduler и self-wake

`JobStore` уже есть, поэтому логично не выбрасывать его, а довести до рабочего состояния.

### Нужны built-in tools

- `system.jobs.schedule_once`
- `system.jobs.schedule_interval`
- `system.jobs.cancel`
- `system.jobs.list`

### Нужен runtime scheduler service

- отдельный tick loop внутри runtime
- хранение задач в `.nagient/jobs/*.json`
- выполнение через `PostSubmitAction` или новый `AgentWakeRequest`

### Что должна уметь job

- разовый запуск
- запуск в конкретное время
- периодический запуск
- synthetic self-message в сессию

### Self-call

Самый чистый вариант:

- job создает synthetic inbound event
- runtime обрабатывает его как обычный user/system event
- у события есть `session_id`, `transport_id`, `event_type = "system_wake"`

## 3.11 Telegram transport: что именно добавить

### Phase 1

- `telegram.sendTyping` через `sendChatAction`
- generalized `telegram.sendChatAction`
- `telegram.editMessage`
- `telegram.deleteMessage`
- `telegram.setReaction`
- richer normalize support для `edited_message`

### Phase 2

- transport-rendered approvals/interactions через inline keyboard
- outbound target presets
- optional media sends: `sendPhoto`, `sendDocument`

### Почему так

- typing сразу улучшает UX
- edit/delete/reaction нужны для живого transport-aware агента
- callback/inline actions идеально подходят под approvals

## 3.12 Workspace access и команды

Здесь фундамент уже хороший.

У модели уже можно дать безопасный доступ через built-in tools:

- `workspace.fs.*`
- `workspace.shell.run`
- `workspace.git.*`

Не хватает только одного: полноценного agent turn loop, который реально передает эти tools модели и умеет исполнять tool calls от provider.

## 4. Поэтапный план реализации

### Фаза 1. Контракты и core runtime

- добавить новый provider contract для structured assistant response
- добавить `AgentRuntimeService`
- добавить `SessionMemoryService`
- добавить `TransportRouterService`
- начать писать transcript в SQLite

### Фаза 2. Memory и notes

- SQLite schema + migrations
- built-in memory tools
- индекс markdown notes
- hard limit + dynamic focus
- summary compaction

### Фаза 3. Workflow и transport-aware UX

- pending workflow matcher
- transport rendering contract
- Telegram inline approval flow
- console fallback flow

### Фаза 4. Scheduler и self-wake

- runtime scheduler loop
- job tools
- synthetic wake events

### Фаза 5. Telegram расширения

- typing
- reaction
- edit/delete
- optional media sends
- tests и contract coverage

## 5. Что я бы менял в проекте в первую очередь

1. Не трогать резко текущий transport runtime contract.
2. Добавить новый agent runtime поверх существующих слоев, а не переписывать их.
3. Память делать на SQLite, а заметки оставить файлами плюс индекс.
4. Multi-transport outbound делать через router/adapter, а не прямым доступом модели к сырым transport plugin методам.
5. Сначала стандартизировать optional transport capabilities, потом расширять Telegram.

## 6. Что уже проверено в текущем репозитории

Локально подтверждено, что базовые unit-тесты по transport/runtime/workspace проходят:

- `tests.unit.test_transport_builtins`
- `tests.unit.test_transport_registry`
- `tests.unit.test_runtime_agent`
- `tests.unit.test_workspace_manager`

Команда:

```bash
PYTHONPATH=src .venv312/bin/python -m unittest \
  tests.unit.test_transport_builtins \
  tests.unit.test_transport_registry \
  tests.unit.test_runtime_agent \
  tests.unit.test_workspace_manager -v
```

Это значит, что текущий фундамент transport polling, Telegram basics и workspace guard уже рабочий и его можно развивать без переписывания с нуля.
