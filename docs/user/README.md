# User Guide

English · [Русская версия](README.ru.md) · [All documentation](../README.md)

This path is for operators. No Python development knowledge is required.

## Recommended Route

1. [Install Nagient](../install.md).
2. Run `nagient setup` and [configure a provider and secrets](../configuration.md).
3. Start a conversation with `nagient chat`.
4. [Install the transports and tools you need](plugins.md).
5. Run `nagient preflight`, then `nagient up` and `nagient status`.

## User Contents

| Article | Use it when... |
| --- | --- |
| [Installation and updates](../install.md) | You are installing, upgrading, or removing Nagient on a computer. |
| [Server deployment](../deploy.md) | You are operating Nagient with Docker Compose. |
| [Commands and daily operations](../commands.md) | You need CLI syntax, chat, status, logs, or lifecycle commands. |
| [Configuration and secrets](../configuration.md) | You are selecting providers, tools, workspace, or secret storage. |
| [Plugin workflow](plugins.md) | You need Telegram, GitHub API, or another external extension. |
| [Environment variables](../env.md) | You are configuring Compose or automation without interactive setup. |
| [Troubleshooting](../troubleshooting.md) | Preflight, startup, Docker, provider, or plugin activation fails. |

## Plugin Installation At A Glance

| Runtime | Open Plugin Hub | Verify |
| --- | --- | --- |
| Personal computer | `nagient plugin install` | `nagient preflight` |
| Docker Compose | `docker compose exec nagient nagient plugin install` | `docker compose exec nagient nagient preflight` |
| Automation | `nagient plugin install <verified-id-or-git-url>` | `nagient plugin list` |
