# User Guide

Language: English | [Русский](README.ru.md)

This section is for operators who want to install, configure, update, and use
Nagient. It does not require Python development knowledge.

## Start Here

- [Install on Linux/macOS/Windows](../install.md)
- [Run without Docker](../install.md#docker-free-local-runtime)
- [Run with Docker Compose](../deploy.md)
- [Find and install plugins](plugins.md)
- [Configure secrets and environment variables](../env.md)
- [Daily CLI commands](../commands.md)
- [Troubleshoot a failed startup](../troubleshooting.md)

## Installation Paths

| Installation | Install a plugin | Verify |
| --- | --- | --- |
| Personal computer installer | `nagient plugin catalog list` then `nagient plugin catalog install <id>` | `nagient preflight` |
| Docker Compose | `docker compose exec nagient nagient plugin catalog list` then `docker compose exec nagient nagient plugin catalog install <id>` | `docker compose exec nagient nagient status` |
| Direct Git repository | `nagient plugin install <url>#<tag>` | `nagient preflight` |

The official catalog is the safe default. `bundled` means the extension is
already present and does not need installation.
