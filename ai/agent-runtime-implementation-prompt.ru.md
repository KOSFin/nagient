# Implementation Prompt For Next AI Agent

Ниже находится рабочий промпт для AI-агента, который будет продолжать разработку Nagient. Этот промпт нужно воспринимать как прямое техническое ТЗ. Он написан так, чтобы новый агент мог начать работу, имея доступ только к текущему репозиторию и его файлам.

---

Ты работаешь в репозитории `Nagient`.

Твоя задача: реализовать следующий большой слой системы Nagient поверх уже существующего platform/control-plane фундамента. Тебе нужно не просто добавить пару файлов, а аккуратно развить архитектуру так, чтобы будущий агентный runtime, tool-плагины, secret handoff, backups, approvals и workspace management были согласованы с уже существующими контрактами проекта.

Работай как сильный системный инженер. Не изобретай параллельную архитектуру рядом с тем, что уже есть. Всегда сначала исследуй текущий код, затем проектируй, затем внедряй, затем покрывай тестами и только после этого обновляй документацию и CI.

## 1. Сначала внимательно изучи проект

Перед любыми изменениями обязательно прочитай и пойми:

- [ai/README.md](./README.md)
- [docs/architecture.ru.md](../docs/architecture.ru.md)
- [docs/architecture.md](../docs/architecture.md)
- [README.ru.md](../README.ru.md)
- [README.md](../README.md)
- [src/nagient/app/settings.py](../src/nagient/app/settings.py)
- [src/nagient/app/configuration.py](../src/nagient/app/configuration.py)
- [src/nagient/app/container.py](../src/nagient/app/container.py)
- [src/nagient/infrastructure/runtime.py](../src/nagient/infrastructure/runtime.py)
- [src/nagient/plugins/base.py](../src/nagient/plugins/base.py)
- [src/nagient/plugins/manager.py](../src/nagient/plugins/manager.py)
- [src/nagient/plugins/registry.py](../src/nagient/plugins/registry.py)
- [src/nagient/providers/base.py](../src/nagient/providers/base.py)
- [src/nagient/providers/manager.py](../src/nagient/providers/manager.py)
- [src/nagient/providers/registry.py](../src/nagient/providers/registry.py)
- [src/nagient/providers/storage.py](../src/nagient/providers/storage.py)
- [src/nagient/application/services/preflight_service.py](../src/nagient/application/services/preflight_service.py)
- [src/nagient/application/services/reconcile_service.py](../src/nagient/application/services/reconcile_service.py)
- [src/nagient/application/services/provider_service.py](../src/nagient/application/services/provider_service.py)
- [src/nagient/cli.py](../src/nagient/cli.py)
- [.github/workflows/ci.yml](../.github/workflows/ci.yml)
- [.github/workflows/release.yml](../.github/workflows/release.yml)

Ты обязан понять, что в проекте уже есть:

- единый bootstrap/reconcile цикл
- transport plugin framework
- provider/auth plugin framework
- CLI и Docker delivery слой
- settings/container/services split
- CI/CD и release/update center

Ты обязан понять, чего в проекте пока нет:

- полноценного agent runtime loop
- workspace sandbox / workspace manager
- tool plugin framework
- backup/checkpoint subsystem
- secret broker / secure interaction workflows
- memory/notes/jobs model
- approval layer для опасных операций

## 2. Нельзя ломать существующие инварианты

Любая новая реализация обязана сохранять и развивать уже существующие контракты проекта.

Нельзя без причины ломать:

- update center contract
- tag-driven release flow
- centralized update logic
- bootstrap/reconcile contract
- transport plugin contract
- provider/auth contract

Если ты меняешь любую из этих моделей, ты обязан одновременно обновить:

- код
- тесты
- документацию
- install scripts / Docker flow, если это их касается
- CI/CD проверки, если новые контракты должны верифицироваться автоматически

## 3. Главная цель текущего этапа

Тебе нужно реализовать основу для настоящего “мозга” Nagient, но не в виде одной монолитной штуки. Нужна модульная, проверяемая и расширяемая система.

На текущем этапе нужно спроектировать и внедрить:

1. `agent runtime core`
2. `tool plugin framework`
3. `workspace manager`
4. `backup/checkpoint manager`
5. `secret broker`
6. `secure interaction workflow`
7. `approval layer`
8. `agent memory/notes/jobs layout`
9. интеграцию всего этого в CLI, runtime, preflight/reconcile, status, docs, tests и CI

Google-интеграции пока не являются приоритетом. Сначала закрой ядро системы, tool-плагины, агент, backup и секреты.

## 4. Архитектурные решения, которые уже приняты и обязательны

### 4.1 Видимая `.nagient/` папка внутри workspace

В рабочем проекте агента должна существовать видимая папка `.nagient/`.

Она нужна для:

- заметок агента
- памяти агента
- планов
- локальных job/spec файлов
- пользовательски понятных служебных файлов агента
- script artifacts, если они не являются чувствительными

В `.nagient/` можно хранить:

- `memory/`
- `notes/`
- `plans/`
- `jobs/`
- `scripts/`

В `.nagient/` нельзя хранить:

- raw секреты
- токены
- credential cache
- приватные auth session payloads
- чувствительное внутреннее состояние рантайма

Чувствительное состояние должно храниться вне workspace, в системных директориях Nagient, по аналогии с тем, как уже хранится часть runtime state в текущей архитектуре.

### 4.2 Агент никогда не должен читать ENV/секреты

Это один из важнейших инвариантов.

Агент может:

- знать имя секрета
- знать, что секрет существует или отсутствует
- знать, к какому тулу или коннектору привязан секрет
- ссылаться на секрет по имени или `secret_ref`

Агент не может:

- читать `secrets.env`
- читать отдельный env-файл тулзов
- получать raw значение секрета в prompt/context
- видеть токены в логах
- извлекать значения через tool outputs

Система должна подставлять значения секретов сама, на уровне рантайма/tool executor/connector layer.

### 4.3 Нужен отдельный `Secret Broker`

Реализуй отдельный слой, который управляет секретами для инструментов и интеграций.

Минимально у него должны быть:

- безопасная загрузка secret metadata
- хранение и обновление секретов без раскрытия их агенту
- binding секрета к connector/tool profile
- резолв `secret_ref` при исполнении инструмента
- redaction в логах
- self-check / validation

Раздели секреты минимум на два класса:

- core/system secrets
- tool/connector secrets

Используй отдельный файл или отдельный storage layout для tool/connector secrets, например:

- `secrets.env` для core
- `tool-secrets.env` или `connector-secrets.env` для tool/connector integrations

Агент должен оперировать именами секретов, а не их значениями.

### 4.4 Transport-driven secure interactions

Нужна система, при которой агент может запросить у пользователя чувствительные данные или подтверждение действия через transport layer, но не увидеть ответ напрямую.

Это обязательный сценарий.

Примеры:

- агент написал плагин и ему нужен API key
- агент хочет попросить у пользователя GitHub token
- агент хочет запросить подтверждение restore backup
- агент хочет попросить секрет для нового connector profile

Нужно реализовать `Secure Interaction Workflow`:

1. Агент создает не обычное сообщение, а специальный interaction request.
2. В request указывается тип действия, transport, текст для пользователя и post-submit plan.
3. Пользователь отвечает через текущий transport.
4. Ответ не попадает в transcript агента.
5. Ответ обрабатывает системный orchestrator.
6. Orchestrator выполняет только заранее разрешенные typed actions.
7. Агент получает только sanitized result:
   - `success`
   - `failed`
   - `cancelled`
   - sanitized logs

Никогда не исполняй произвольную shell-строку, присланную агентом как post-submit action.

Разрешены только строго типизированные post-submit actions, например:

- `secret.store`
- `connector.bind_secret`
- `config.patch`
- `tool.invoke`
- `backup.restore`
- `system.reconcile`
- `agent.resume`
- `agent.resume_with_error`

### 4.5 Approval layer для ключевых действий

Нужна отдельная прослойка одобрения опасных/важных действий.

Это обязательная система.

Агент не должен напрямую выполнять некоторые действия, даже если он может их запросить.

Он должен создавать `approval request`, а система уже:

- отправляет запрос в активный transport
- ждет ответа пользователя
- при `approve` исполняет действие
- при `reject` возвращает агенту структурированный отказ

Примеры действий, которые должны проходить через approval layer:

- restore backup
- destructive git restore/reset-like operations
- dangerous filesystem actions
- операции, помеченные high-risk policy
- возможно shell-команды повышенного риска

В контексте Telegram или другого транспорта агент должен уметь только инициировать запрос. Исполнение должно быть системным, а не “агент сам все сделал”.

### 4.6 Backup-система должна быть локальной, внутренней и независимой

Backup-коммиты не должны делаться “от имени существующего аккаунта пользователя”.

Нужны внутренние локальные snapshots Nagient.

Рекомендуемая модель:

- локальные git-based backup snapshots
- отдельные внутренние refs или отдельная внутренняя backup-ветка
- либо отдельный backup-repository, если workspace не является git-репозиторием

Автор snapshot-коммитов может быть фиксированным локальным служебным identity, например:

- `Nagient Backup <nagient@local>`

Backup snapshots:

- не должны пушиться по умолчанию
- не должны засорять рабочую пользовательскую ветку
- должны быть удобны для restore/list/diff/export

Нужны tool/service операции:

- `backup.create`
- `backup.list`
- `backup.diff`
- `backup.restore`
- `backup.prune`
- `backup.export`

Restore должен быть интегрирован с approval layer.

### 4.7 Batch-based safety

Снимок состояния нужно делать не перед каждым микроскопическим файловым действием, а перед каждым write-capable batch/tool-execution group.

То есть:

- один логический batch действий агента
- один checkpoint перед началом
- дальнейшее выполнение тулзов
- если нужно, откат возможен к checkpoint

### 4.8 Shell должен быть отдельным built-in tool

Shell не должен быть обычным пользовательским плагином.

Нужен отдельный встроенный инструмент:

- с отдельным логированием
- с отдельной политикой рисков
- с интеграцией в backup/checkpoint flow
- с ограничением рабочей директории через workspace manager
- с возможностью в будущем пропускать команды через approval layer

### 4.9 Unsafe mode должен существовать

В системе должен быть `unsafe mode`.

Это означает, что должен существовать режим, в котором агент работает вне обычных ограничений workspace-bound execution.

Но реализация должна быть честной и явно различать:

- bounded workspace mode
- unsafe host-level mode

Режим должен быть виден в config/status/runtime metadata.

### 4.10 Google пока не приоритет

Не трать основной объем реализации на Google Calendar/Drive на этом этапе.

Сначала закрой:

- workspace
- shell/fs/git
- backup
- secure interactions
- approvals
- GitHub-oriented tool flow
- агентный runtime

## 5. Реализуй новый слой: Tool Plugin Framework

Сейчас в проекте уже есть transport plugins и provider plugins. Нужно добавить третий класс плагинов: `tool plugins`.

Это должен быть полноценный системный слой, а не ad-hoc функции.

Минимально tool-plugin contract должен поддерживать:

- plugin manifest
- python entrypoint
- display name
- version
- namespace
- exposed functions
- input schema
- output schema
- required config
- optional config
- secret bindings / secret refs
- required connectors
- self-test
- healthcheck
- permissions / capability declarations
- side effect classification
- confirmation / approval policy
- dry-run support, где это возможно

Нужны manager/registry/scaffold/test helpers, по аналогии с уже существующими transport/provider системами.

Плагинная система должна быть согласована со стилем текущего проекта, а не придумана в другом стиле.

## 6. Первые built-in tools, которые стоит реализовать

Минимальный первый набор:

- `workspace.fs`
- `workspace.shell`
- `workspace.git`
- `transport.interaction`
- `system.backup`
- `system.reconcile`
- `github.api`

Опционально, если архитектура просит это явно:

- `workspace.search`
- `workspace.write`
- `workspace.read`
- `system.status`

Но не распыляй систему на слишком много категорий. Лучше меньше, но с правильным контрактом, testability и policy control.

## 7. GitHub-интеграция: приоритетная внешняя интеграция

Google можно отложить. GitHub сейчас важнее.

Нужно строить схему так, чтобы агент мог работать с GitHub через отдельный аккаунт/токен, который дает пользователь.

Важно:

- агент не видит токен
- токен хранится как secret
- агент оперирует только `secret_ref`
- система подставляет токен на уровне исполнения

Желательно поддержать:

- GitHub API actions
- создание/обновление issue/PR в будущем
- repository metadata calls
- а также локальные git-операции в workspace через built-in git/shell tools

Не смешивай:

- локальный `git`
- GitHub HTTP API

Это разные слои, даже если оба связаны с GitHub.

## 8. Реализуй Agent Runtime Core

Нужен уже не heartbeat-заглушка, а настоящий каркас агентного рантайма.

Но не начинай с “свободного текста”. Сделай нормализованный внутренний контракт.

Минимально тебе нужны сущности уровня:

- `AgentTurnRequest`
- `AgentTurnContext`
- `AgentTurnResult`
- `AssistantResponse`
- `NormalizedToolCall`
- `ToolExecutionRequest`
- `ToolExecutionResult`
- `InteractionRequest`
- `ApprovalRequest`
- `NotificationIntent`
- `ConfigMutationIntent`

Требования:

- отделяй основной ответ пользователю от side effects
- не заставляй модель каждый раз выбирать транспорт для основного ответа
- активная пользовательская сессия уже знает transport
- transport-specific функции вызываются только как явные side-effect actions

Модель должна иметь возможность:

- ответить пользователю
- запросить tool call
- запросить secure interaction
- запросить approval
- запросить reconcile/restart workflow
- получить structured result от предыдущего шага

Пока не нужно строить полный production-grade planning engine. Но внутренний turn contract должен быть правильным, чтобы потом не переписывать половину проекта.

## 9. Workspace Manager

Реализуй отдельный слой управления рабочей средой агента.

Он должен:

- определять workspace root
- создавать `.nagient/` внутри workspace
- обеспечивать path guards
- ограничивать built-in tools текущим workspace в bounded mode
- поддерживать unsafe mode
- уметь хранить workspace metadata
- уметь интегрироваться с backup manager
- уметь интегрироваться с shell/git tools

Если workspace является git-репозиторием, используй это.
Если нет, система все равно должна работать.

Продумай, как хранить:

- workspace id
- workspace policy
- mode
- created/updated metadata
- known backup state

## 10. Память, заметки, jobs

Агент должен иметь рабочее пространство для своих заметок и служебных файлов.

В `.nagient/` предусмотрены:

- `memory/`
- `notes/`
- `plans/`
- `jobs/`
- `scripts/`

Нужна минимальная модель:

- агент может писать туда не-секретные артефакты
- агент может ссылаться на них в своих шагах
- система может использовать их при wake/scheduler workflow

Также нужна основа под jobs/scheduler:

- отложенный запуск
- запуск в конкретное время
- периодический запуск
- wake-after-event

Это должна быть системная job model, а не “агент сам руками пишет cron”.

## 11. Secure post-response actions

Обязательно реализуй сценарий, когда агент формирует запрос пользователю, а после ответа система сама выполняет действия без раскрытия содержимого ответа агенту.

Пример обязательного поведения:

1. Агент просит у пользователя GitHub token.
2. Пользователь отправляет токен через transport.
3. Система сохраняет токен в отдельное secret storage.
4. Система валидирует привязку токена.
5. Система вызывает self-test инструмента/connector-а.
6. Система либо возвращает агенту sanitized success, либо sanitized error.

То же самое должно работать и для:

- API keys
- webhook secrets
- approvals
- restore workflows

## 12. Approval flow должен быть transport-aware

Approval flow должен уметь жить поверх текущего transport plugin layer.

Это значит:

- transport должен уметь получать approval request
- transport должен уметь вернуть approve/reject/cancel
- approval должен быть связан с системным pending-action id
- результат approval не должен ломать transcript/session state

Продумай единый contract так, чтобы transport-plugins в будущем могли красиво рендерить:

- кнопки подтверждения
- inline actions
- popup-like UX

Но базовая модель должна работать и для CLI/console transport.

## 13. Реализуй это по фазам, а не хаотично

Рекомендуемый порядок:

1. Исследуй текущий код и зафиксируй точки интеграции.
2. Спроектируй новые domain/entities и service contracts.
3. Добавь `tool plugin` слой.
4. Добавь `workspace manager`.
5. Добавь `backup/checkpoint manager`.
6. Добавь `secret broker`.
7. Добавь `secure interaction` и `approval layer`.
8. Добавь built-in tools.
9. Добавь skeleton agent runtime turn loop.
10. Обнови CLI/status/preflight/reconcile/runtime.
11. Обнови docs.
12. Обнови CI/CD.

Не пытайся в самом начале за один шаг сделать “весь мозг агента”. Сначала зафиксируй правильные контракты и инфраструктуру выполнения.

## 14. Стандарты качества: тесты обязательны на все

Это критично.

Ты обязан покрывать тестами буквально каждую функцию и каждый важный контракт. Система должна работать как часы. Поведение должно быть предсказуемым, проверяемым и устойчивым к регрессиям.

Требование не “написать несколько тестов”. Требование: построить полноценный test matrix.

Обязательные виды тестов:

- unit tests
- integration tests
- smoke tests
- contract tests
- fault-injection tests
- regression tests
- CLI tests
- Docker-related smoke checks, где это уместно

Что должно быть покрыто:

- каждая новая функция
- каждый parser/serializer
- каждый manager/service
- каждый manifest contract
- каждая policy decision branch
- path guard behavior
- unsafe mode behavior
- backup create/list/restore flows
- approval flows
- secure interaction flows
- secret broker behavior
- redaction behavior
- tool execution behavior
- plugin registry/loader/scaffold
- scheduler/job persistence behavior
- runtime turn contracts
- error handling branches

Если появляется сложная ветка логики, для нее нужен тест.
Если появляется edge case, для него нужен тест.
Если появляется fallback, для него нужен тест.
Если есть гарантия безопасности, она должна быть покрыта тестом.

Недопустимо оставлять “очевидные места” без тестов.

## 15. CI/CD нужно усилить

Тебе нужно не только написать тесты, но и встроить их в CI/CD.

Проверь текущий pipeline и расширь его при необходимости.

Нужно:

- включить coverage в CI, если еще не включен полноценно
- задать fail-under threshold
- запускать новые test lanes автоматически
- не ломать существующий release flow
- добавить smoke/contract checks для новых подсистем, если это оправдано

Если новая система требует отдельного test job, добавь его.
Если нужны fixtures, создай их.
Если нужны helper-утилиты для тестирования плагинов, добавь их.

## 16. Документация обязательна

Если ты внедряешь новую подсистему, ты обязан обновить документацию проекта.

Минимально проверь и при необходимости обнови:

- [ai/README.md](./README.md)
- [docs/architecture.ru.md](../docs/architecture.ru.md)
- [docs/architecture.md](../docs/architecture.md)
- [README.ru.md](../README.ru.md)
- [README.md](../README.md)
- developer docs, если они затрагиваются

Документация должна честно отражать текущее состояние проекта. Не пиши, что система умеет то, чего на самом деле еще нет.

## 17. Общие правила реализации

- Сохраняй существующий стиль проекта.
- Предпочитай stdlib и минимальные зависимости там, где это разумно.
- Делай контракты явными и сериализуемыми.
- Не смешивай transport/provider/tool layers.
- Не давай агенту доступ к raw секретам.
- Не обманывай с безопасностью: если режим unsafe, он должен быть явно unsafe.
- Не исполняй произвольные post-submit команды от агента.
- Используй typed workflows, policy checks и approval gating.
- Не ломай bootstrap/reconcile модель.
- Все новые состояния и файлы должны иметь понятное место в файловой структуре.
- Все, что влияет на надежность, должно иметь tests.

## 18. Что должно получиться в итоге

После твоей работы в репозитории должна появиться рабочая база для настоящего Nagient agent runtime:

- tool plugin framework
- workspace manager
- backup/checkpoint subsystem
- secret broker
- secure interaction workflows
- approval layer
- built-in tools для shell/fs/git/backup/reconcile/transport interaction/github
- начальный agent runtime turn contract
- расширенные тесты
- усиленный CI
- обновленная документация

Ты не должен ограничиваться “архитектурным наброском”. Нужно дойти до реального рабочего кода, тестов и интеграции в проект.

Если какая-то часть слишком большая для одной итерации, сначала реализуй минимально правильный вертикальный срез, но так, чтобы он:

- соответствовал архитектуре
- был протестирован
- не требовал потом полной переделки

## 19. Ожидаемое поведение при работе

Во время работы:

- сначала анализируй код
- потом составляй четкий поэтапный план
- затем реализуй
- после каждой значимой подсистемы прогоняй тесты
- в конце обязательно прогоняй весь доступный test suite

Если находишь несоответствие документации и кода:

- исправляй либо код, либо документацию
- не оставляй противоречие в репозитории

Если для новой функциональности нужен config/schema/storage change:

- обнови все связанные слои сразу
- добавь миграционную логику или backward-compatible handling, если это необходимо

## 20. Финальная проверка перед завершением

Перед тем как считать задачу завершенной, проверь:

- код реализован
- тесты написаны
- тесты встроены в CI
- docs обновлены
- transport/provider/tool/workspace/backup/secret contracts согласованы
- агент не может читать секреты
- approval flow работает
- secure interaction flow работает
- backup restore gated через approval
- `.nagient/` используется правильно
- чувствительное состояние не лежит в workspace

Если что-то из этого не выполнено, задача не завершена.

---

Работай внимательно. Здесь важнее корректная системная архитектура и надежность, чем скорость. Nagient должен быть платформой, которая отрабатывает стабильно, а не набором loosely connected features.
