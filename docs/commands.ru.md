# Команды

Язык: [English](commands.md) | Русский

## 1. Короткие команды (рекомендуется)

После установки используйте `nagient` для ежедневной эксплуатации.

Linux/macOS:

```bash
~/.nagient/bin/nagient help
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagient.ps1" help
```

### 1.1 Команды управления runtime

- `up` или `start`: запуск контейнера
- `down` или `stop`: остановка контейнера
- `restart`: перезапуск
- `status`: статус контейнера + `nagient status`
- `doctor`: `nagient doctor`
- `preflight`: `nagient preflight`
- `reconcile`: `nagient reconcile`
- `logs [service]`: поток логов
- `shell`: shell в контейнере
- `exec <cmd...>`: выполнить команду в контейнере
- `update`: обновление до latest
- `remove` или `uninstall`: удаление runtime

## 2. Полные команды `nagient` CLI

Формат:

```bash
nagient <command> [subcommand] [options]
```

### 2.1 Базовые

- `nagient version`
- `nagient init [--force] [--format text|json]`
- `nagient status [--format text|json]`
- `nagient doctor [--format text|json]`
- `nagient paths [--format text|json]`
- `nagient preflight [--format text|json]`
- `nagient reconcile [--format text|json]`
- `nagient serve [--once]`
- `nagient setup`
- `nagient chat [message] [--provider <id>] [--system <prompt>] [--interactive] [--format text|json]`

`nagient setup` открывает интерактивный мастер настройки. Во всех меню `0` возвращает назад или завершает setup.

`nagient paths` показывает алиасы путей: `@home`, `@config`, `@secrets`, `@plugins`, `@providers` и другие. Эти алиасы можно использовать в setup и path-параметрах CLI.

`nagient chat` — это консольная точка входа для общения из CLI. Команда использует выбранный provider или `[agent].default_provider`, если `--provider` не передан.

### 2.1.1 Интерактивные команды setup

- `nagient setup provider <provider_id> ...`
- `nagient setup transport <transport_id> ...`
- `nagient setup tool <tool_id> ...`
- `nagient setup workspace [--root <path-or-alias>] [--mode bounded|unsafe]`
- `nagient setup paths [--secrets-file <path-or-alias>] [--tool-secrets-file <path-or-alias>] [--plugins-dir <path-or-alias>] [--tools-dir <path-or-alias>] [--providers-dir <path-or-alias>] [--credentials-dir <path-or-alias>]`

### 2.2 Transport

- `nagient transport list [--format text|json]`
- `nagient transport scaffold --plugin-id <id> [--output <dir>] [--force] [--format text|json]`

### 2.3 Provider

- `nagient provider list [--format text|json]`
- `nagient provider scaffold --plugin-id <id> [--output <dir>] [--force] [--format text|json]`
- `nagient provider models <provider_id> [--format text|json]`

### 2.4 Auth

- `nagient auth status [provider_id] [--verify] [--format text|json]`
- `nagient auth login <provider_id> [--api-key <key>] [--token <token>] [--secret-name <name>] [--format text|json]`
- `nagient auth complete <provider_id> --session-id <id> [--callback-url <url>] [--code <code>] [--format text|json]`
- `nagient auth logout <provider_id> [--format text|json]`

### 2.5 Tool

- `nagient tool list [--format text|json]`
- `nagient tool scaffold --plugin-id <id> [--output <dir>] [--force] [--format text|json]`
- `nagient tool invoke <function_name> [--tool-id <id>] [--args-json '{...}'] [--dry-run] [--auto-approve] [--format text|json]`

### 2.6 Interaction и approval

- `nagient interaction list [--format text|json]`
- `nagient interaction submit <request_id> [--response <value>] [--cancel] [--format text|json]`
- `nagient approval list [--format text|json]`
- `nagient approval respond <request_id> --decision approve|reject|cancel [--format text|json]`

### 2.7 Update, manifest, migrations

- `nagient update check [--channel stable] [--manifest-ref <url-or-path>] [--current-version <ver>] [--format text|json]`
- `nagient manifest render --version <ver> --channel <name> --base-url <url> --docker-image <image> [--published-at <ISO8601>] [--summary <text>] [--output <file>]`
- `nagient migrations plan --manifest-ref <url-or-path> --current-version <ver> [--format text|json]`

### 2.8 Agent turn

- `nagient agent turn --request-file <path.json> [--format text|json]`

`nagient agent turn` — это низкоуровневый интерфейс для структурированных workflow.

Для обычной работы в терминале лучше использовать:

- `nagient chat`
- `nagient setup`
