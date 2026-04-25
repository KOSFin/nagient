# Контекст AI-проекта

Язык: [English](README.md) | Русский

Этот документ предназначен для AI-агентов и автоматизации, которые продолжают разработку Nagient.

## 1. Назначение проекта

Nagient проектируется как агентная платформа: сначала delivery/update контракты, затем на их базе расширение runtime-интеллекта.

Цели платформы:

- установка через Docker image
- установка через shell-скрипт
- установка через PowerShell-скрипт
- автоматическая публикация релизов
- централизованное управление обновлениями
- миграции в рамках релизной модели
- будущие каналы уведомлений не только через CLI

## 2. Текущее состояние

Уже реализован фундамент:

- Python package с CLI entrypoints
- разделение app/application/domain/infrastructure
- bootstrap и reconcile цикл активации runtime
- transport plugin framework и registry
- provider framework и auth workflows
- tool plugin framework и встроенные workspace-tools
- менеджер workspace layout и path guards
- backup/checkpoint подсистема
- secret broker с границами redaction
- secure interaction и approval workflow stores
- структурированный agent turn contract и executor
- генерация release metadata и update center flow
- CI, release automation, smoke/integration/unit tests

Важно: репозиторий пока является платформенным каркасом, а не полностью автономным runtime-агентом.

## 3. Карта репозитория

Ключевые модули:

- `src/nagient/cli.py`
- `src/nagient/app/settings.py`
- `src/nagient/app/configuration.py`
- `src/nagient/app/container.py`
- `src/nagient/application/services/`
- `src/nagient/infrastructure/`
- `src/nagient/plugins/`
- `src/nagient/providers/`
- `src/nagient/tools/`
- `src/nagient/workspace/`
- `src/nagient/security/`
- `src/nagient/migrations/`

Слой доставки:

- `scripts/install.sh`, `scripts/install.ps1`
- `scripts/update.sh`, `scripts/update.ps1`
- `scripts/uninstall.sh`, `scripts/uninstall.ps1`
- `scripts/release/`
- `metadata/update-center/`
- `.github/workflows/`

## 4. Инварианты, которые нельзя ломать

- update center contract: `channels/<channel>.json` и `manifests/<version>.json`
- tag-driven release flow: `vX.Y.Z`
- централизованная логика обновления через manifests
- bootstrap/reconcile цикл и safe-mode semantics
- границы transport/provider/tool/workspace/security

Если меняется один из контрактов, обновляются код, скрипты и тесты одновременно.

## 5. Текущая CLI-поверхность

- `nagient init|status|doctor|preflight|reconcile|serve`
- `nagient transport list|scaffold`
- `nagient provider list|scaffold|models`
- `nagient auth status|login|complete|logout`
- `nagient tool list|scaffold|invoke`
- `nagient interaction list|submit`
- `nagient approval list|respond`
- `nagient update check`
- `nagient manifest render`
- `nagient migrations plan`
- `nagient agent turn --request-file ...`

## 6. Фокус тестирования

Регрессии должны покрывать:

- parsing/serialization update metadata
- loading settings/config и обработку путей
- preflight/reconcile поведение в safe mode
- registries/scaffold generators для плагинов
- гарантию redaction в secret broker
- проверки безопасности workspace
- контракты release scripts и smoke checks

## 7. Рекомендуемый порядок развития

1. Ввести persistent runtime state model.
2. Расширить provider abstraction для model execution.
3. Реализовать task loop и scheduling semantics.
4. Усилить secure tool runtime и approval gates.
5. Добавить внешние поверхности (API, webhooks, richer UX).

## 8. Рабочий промпт

Файлы implementation prompt:

- Русский: [agent-runtime-implementation-prompt.ru.md](agent-runtime-implementation-prompt.ru.md)
- English: [agent-runtime-implementation-prompt.md](agent-runtime-implementation-prompt.md)
