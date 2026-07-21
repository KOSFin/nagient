# Plugin Hub

English · [Русская версия](plugins.ru.md) · [Documentation index](README.md)

Nagient keeps optional integrations outside the core package. A plugin has its own repository, manifest, version, dependencies, documentation, and release cycle. Installed plugins live under `~/.nagient` and are never copied into the Python package.

## Open The Installer

```bash
nagient plugin install
```

In an interactive terminal, Plugin Hub shows every verified external plugin with its type and `installed` or `available` status. Choose a plugin or select the Git URL option. In a non-interactive shell, the same command prints the verified catalog and ready-to-run install commands instead of waiting for input.

## Install Directly

A verified short ID is the simplest reproducible source:

```bash
nagient plugin install nagient.telegram
nagient plugin install nagient.github_api
```

Nagient resolves the reviewed repository and pinned release from the catalog. A compatible Git repository can also be installed without a prefix:

```bash
nagient plugin install https://github.com/owner/nagient-plugin.git
nagient plugin install https://github.com/owner/nagient-plugin.git --ref v1.2.0
```

Use `--force` to reinstall, `--no-dependencies` for a repository that needs no isolated environment, and `--format json` in automation.

## Verified Catalog

| Plugin | Family | Status | Install |
| --- | --- | --- | --- |
| [Console Transport](commands.md#21-core) | Transport | Bundled | No installation needed |
| [Webhook Transport](plugin-contracts.md) | Transport | Bundled | No installation needed |
| [Telegram Transport](https://github.com/KOSFin/nagient-transport-telegram) | Transport | Verified external | `nagient plugin install nagient.telegram` |
| [GitHub API Tool](https://github.com/KOSFin/nagient-tool-github-api) | Tool | Verified external | `nagient plugin install nagient.github_api` |

List the machine-readable catalog or filter it by family:

```bash
nagient plugin catalog list
nagient plugin catalog list --family transport
nagient plugin catalog list --format json
```

## Configure An Installed Plugin

Installation makes a plugin discoverable; configuration decides whether a profile is enabled. Every manifest declares its own fields. Environment overrides follow one shape:

```text
NAGIENT_<FAMILY>__<PROFILE_ID>__<FIELD>=value
```

Telegram example:

```env
NAGIENT_TRANSPORT__TELEGRAM__PLUGIN=nagient.telegram
NAGIENT_TRANSPORT__TELEGRAM__ENABLED=true
NAGIENT_TRANSPORT__TELEGRAM__BOT_TOKEN_SECRET=TELEGRAM_BOT_TOKEN
NAGIENT_TRANSPORT__TELEGRAM__ALLOWED_USER_IDS=123456789
TELEGRAM_BOT_TOKEN=123456:replace-me
```

GitHub API example:

```env
NAGIENT_TOOL__GITHUB_API__PLUGIN=nagient.github_api
NAGIENT_TOOL__GITHUB_API__ENABLED=true
NAGIENT_TOOL__GITHUB_API__TOKEN_SECRET=GITHUB_TOKEN
GITHUB_TOKEN=github_pat_replace_me
```

Secret fields contain a secret name. Keep the actual value in the environment, `secrets.env`, `tool-secrets.env`, or the corresponding JSON secret override.

## Docker Compose

Use the same Plugin Hub inside the persistent container:

```bash
docker compose exec nagient nagient plugin install
docker compose exec nagient nagient plugin install nagient.telegram
docker compose exec nagient nagient preflight
docker compose restart nagient
```

For unattended first boot, pin sources in `.env`:

```env
NAGIENT_PLUGIN_SPECS=https://github.com/KOSFin/nagient-transport-telegram.git#v0.2.1,https://github.com/KOSFin/nagient-tool-github-api.git#v0.2.1
```

The persistent `./data` mount keeps installed plugins across container restarts.

## Inspect, Update, And Remove

```bash
nagient plugin list
nagient plugin install nagient.telegram --force
nagient plugin remove nagient.telegram
nagient preflight
```

Reinstalling a verified ID uses its currently pinned catalog ref. For an arbitrary repository, pass the desired `--ref` explicitly.

## Trust Model

`verified` means the Nagient catalog pins a reviewed source and ref. It does not sandbox arbitrary plugin code. Before installing an unverified URL, review its manifest, source, dependencies, permissions, and network behavior. Keep workspace mode `bounded` unless a workflow explicitly requires broader access.

Plugin authors should start from the [official template](https://github.com/KOSFin/nagient-plugin-template) and continue with [Build your first plugin](PLUGIN_DEVELOPMENT.md).
