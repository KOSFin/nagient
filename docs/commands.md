# Commands

Language: English | [Русский](commands.ru.md)

## 1. Shortcut commands (recommended)

After installation, use `nagientctl` for day-to-day operations.

Linux/macOS:

```bash
~/.nagient/bin/nagientctl help
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagientctl.ps1" help
```

### 1.1 Runtime control commands

- `up` or `start`: start container
- `down` or `stop`: stop container
- `restart`: restart container
- `status`: container status + `nagient status`
- `doctor`: run `nagient doctor`
- `preflight`: run `nagient preflight`
- `reconcile`: run `nagient reconcile`
- `logs [service]`: stream logs
- `shell`: open shell in container
- `exec <cmd...>`: execute command in container
- `update`: update to latest
- `remove` or `uninstall`: uninstall runtime

## 2. Full `nagient` CLI commands

Format:

```bash
nagient <command> [subcommand] [options]
```

### 2.1 Core

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

`nagient setup` opens the interactive setup wizard. Every menu supports `0` to go back or exit.

`nagient paths` shows path aliases such as `@home`, `@config`, `@secrets`, `@plugins`, and `@providers`. These aliases can be used in setup prompts and path-oriented CLI flags.

`nagient chat` is the CLI console entrypoint. It uses the selected provider, or `[agent].default_provider` when `--provider` is omitted.

### 2.1.1 Interactive setup shortcuts

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

### 2.6 Interaction and approval

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

`nagient agent turn` is the low-level structured workflow surface.

For normal terminal usage, prefer:

- `nagient chat`
- `nagient setup`
