# Nagient

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-native-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![Releases](https://img.shields.io/badge/Releases-tag--driven-F97316?logo=git&logoColor=white)](.github/workflows/release.yml)
[![Update Center](https://img.shields.io/badge/Update%20Center-Pages%20ready-222222?logo=githubpages&logoColor=white)](.github/workflows/update-center.yml)
[![Auto Tag](https://img.shields.io/badge/Tags-auto--create-111827?logo=git&logoColor=white)](.github/workflows/auto-tag.yml)
[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-auto--publish-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-16A34A.svg)](LICENSE)
[![Dev Guide](https://img.shields.io/badge/Docs-Developer-0F766E)](developer/README.md)
[![AI Context](https://img.shields.io/badge/Docs-AI-7C3AED)](ai/README.md)

🇺🇸 English | 🇷🇺 [Русский](README.ru.md)

> Lightweight Docker-native agent platform with centralized updates, scripted installs, and tag-driven releases.

Nagient is building a lightweight agent runtime with a distribution model ready from the start: Docker image delivery, `sh` and `ps1` installers, centralized update manifests, and CI/CD around tagged releases.

The core agent assembly is still in progress. What already exists here is the platform layer around it: release automation, update center, installation scripts, Docker runtime scaffold, config bootstrap and reconcile commands, transport plugin scaffolds, test lanes, and repository structure for future agent development.

## Quick Links

- 🧑‍💻 [Developer Guide](developer/README.md)
- 🤖 [AI Context](ai/README.md)
- 🏗️ [Architecture Notes](docs/architecture.md)

## Install Surface

```bash
docker pull docker.io/<dockerhub-namespace>/nagient:<tag>
curl -fsSL <update-base-url>/<tag>/install.sh | bash
pwsh -Command "iwr <update-base-url>/<tag>/install.ps1 -UseBasicParsing | iex"
```

Detailed setup, variables, release flow, and domain configuration live in [developer/README.md](developer/README.md).

## Runtime Bootstrap

Nagient now uses a unified bootstrap flow across local CLI and Docker:

```bash
nagient init
nagient preflight --format json
nagient reconcile --format json
```

The same runtime layout is used everywhere:

- `config.toml` for non-secret runtime configuration
- `secrets.env` for transport/provider secrets
- `plugins/` for custom Python transport plugins

See [developer/README.md](developer/README.md) for the full command reference and Docker/Compose layout.
