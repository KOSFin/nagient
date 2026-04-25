# Команды

Язык: [English](commands.md) | Русский

## 1. Короткие команды (рекомендуется)

После установки используйте `nagientctl` для ежедневной эксплуатации.

Linux/macOS:

```bash
~/.nagient/bin/nagientctl help
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagientctl.ps1" help
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
- `nagient preflight [--format text|json]`
- `nagient reconcile [--format text|json]`
- `nagient serve [--once]`

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
