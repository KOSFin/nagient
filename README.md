# Nagient

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-native-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![Releases](https://img.shields.io/badge/Releases-tag--driven-F97316?logo=git&logoColor=white)](.github/workflows/release.yml)
[![Update Center](https://img.shields.io/badge/Update%20Center-Pages%20ready-222222?logo=githubpages&logoColor=white)](.github/workflows/update-center.yml)
[![Auto Tag](https://img.shields.io/badge/Tags-auto--create-111827?logo=git&logoColor=white)](.github/workflows/auto-tag.yml)
[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-parampo%2Fnagient-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/parampo/nagient)
[![License](https://img.shields.io/badge/License-MIT-16A34A.svg)](LICENSE)

🇺🇸 English | 🇷🇺 [Русский](README.ru.md)

Docker-native agent platform with centralized updates, scripted installation, and tag-driven releases.

Nagient is designed for predictable installation and updates on Linux, macOS, and Windows.

## Install Latest Stable

### Linux and macOS

```bash
curl -fsSL https://ngnt-in.ruka.me/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://ngnt-in.ruka.me/install.ps1 | iex
```

### Docker image

```bash
docker pull docker.io/parampo/nagient:latest
```

The installer creates a local runtime in `~/.nagient` and starts Nagient via Docker Compose.

After installation, use one short control command instead of long Docker Compose commands:

```bash
~/.nagient/bin/nagientctl help
```

Detailed documentation:

- English index: [docs/README.md](docs/README.md)
- Russian index: [docs/README.ru.md](docs/README.ru.md)

## Upgrade and Remove

Use the shortcut command:

```bash
~/.nagient/bin/nagientctl update
```

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagientctl.ps1" update
```

Remove installation:

```bash
~/.nagient/bin/nagientctl remove
```

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME/.nagient/bin/nagientctl.ps1" remove
```

To remove all local runtime data, set `NAGIENT_PURGE=true` before running uninstall.

## Quick Start

1. Run installer for your platform.
2. Edit `~/.nagient/config.toml`.
3. Put provider secrets into `~/.nagient/secrets.env`.
4. Run short commands:

```bash
~/.nagient/bin/nagientctl up
~/.nagient/bin/nagientctl status
~/.nagient/bin/nagientctl logs
```

## Short Command Surface

- `nagientctl up|down|restart`
- `nagientctl status|doctor|preflight|reconcile`
- `nagientctl logs [service]`
- `nagientctl update|remove`

## Full CLI Surface

- `nagient init`, `nagient preflight`, `nagient reconcile`, `nagient serve`
- `nagient transport list|scaffold`
- `nagient provider list|scaffold|models`
- `nagient auth status|login|complete|logout`
- `nagient tool list|scaffold|invoke`
- `nagient interaction list|submit`, `nagient approval list|respond`
- `nagient update check`, `nagient manifest render`, `nagient migrations plan`
- `nagient agent turn --request-file ...`

Full command reference with flags is in [docs/README.md](docs/README.md).

## Runtime Flow

```mermaid
flowchart LR
	A[Install script] --> B[~/.nagient]
	B --> C[docker compose up -d]
	C --> D[entrypoint]
	D --> E[nagient reconcile]
	E --> F[nagient serve]
	F --> G[state and logs]
```

## Notes

- Architecture (EN): [docs/architecture.md](docs/architecture.md)
- Architecture (RU): [docs/architecture.ru.md](docs/architecture.ru.md)
- License: [LICENSE](LICENSE)
