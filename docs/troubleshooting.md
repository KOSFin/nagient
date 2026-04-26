# Troubleshooting

Language: English | [Русский](troubleshooting.ru.md)

## Docker is required

Symptom: installer fails with a Docker-related error.

Check:

1. Docker is installed.
2. Docker daemon is running.
3. `docker` is available in `PATH`.
4. `docker compose version` succeeds.
5. `docker info` succeeds.

Typical macOS symptom:

```text
failed to connect to the docker API at unix:///Users/<user>/.docker/run/docker.sock
```

This usually means Docker Desktop is not running yet.

## Apple Silicon image mismatch

Symptom:

```text
no matching manifest for linux/arm64/v8 in the manifest list entries
```

Cause: the published Docker tag does not include an `arm64` image yet.

Temporary workaround on Apple Silicon:

```bash
DOCKER_DEFAULT_PLATFORM=linux/amd64 curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

This runs the `amd64` image through emulation until a multi-arch release is published.

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
~/.nagient/bin/nagient preflight
~/.nagient/bin/nagient reconcile
~/.nagient/bin/nagient status
```

## Shortcut for long `nagient` path

Define an alias.

Linux/macOS:

```bash
alias ng='~/.nagient/bin/nagient'
ng status
```

PowerShell:

```powershell
Set-Alias ng "$HOME/.nagient/bin/nagient.ps1"
ng status
```
