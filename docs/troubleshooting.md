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

Cause: the update center is serving an unrendered template or a stale branch snapshot instead of the rendered bootstrap asset.

Check:

1. `Settings -> Pages` is configured for `GitHub Actions` or the `gh-pages` branch.
2. Repository variable `UPDATE_BASE_URL` points to the public update-center URL.
3. After changing `UPDATE_BASE_URL` or `CUSTOM_DOMAIN`, rerun `Update Center`.
4. `https://your-domain/install.sh` does not contain `__NAGIENT_UPDATE_BASE_URL__`.

Use:

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

or

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

Notes:

- `NAGIENT_UPDATE_BASE_URL` is not a GitHub repository variable.
- Installers embed it automatically from `UPDATE_BASE_URL`.

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
