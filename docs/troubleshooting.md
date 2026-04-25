# Troubleshooting

Language: English | [Русский](troubleshooting.ru.md)

## Docker is required

Symptom: installer fails with a Docker-related error.

Check:

1. Docker is installed.
2. Docker daemon is running.
3. `docker` is available in `PATH`.

## NAGIENT_UPDATE_BASE_URL is not configured

Symptom: install/update script fails.

Cause: running template script from repository checkout instead of published release asset.

Use:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

or

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

## preflight/reconcile error

Check:

1. Provider is enabled in `config.toml`.
2. Required secrets exist in `secrets.env`.
3. Custom plugins are available.

Commands:

```bash
~/.nagient/bin/nagientctl preflight
~/.nagient/bin/nagientctl reconcile
~/.nagient/bin/nagientctl status
```

## Shortcut for long `nagientctl` path

Define an alias.

Linux/macOS:

```bash
alias ng='~/.nagient/bin/nagientctl'
ng status
```

PowerShell:

```powershell
Set-Alias ng "$HOME/.nagient/bin/nagientctl.ps1"
ng status
```
