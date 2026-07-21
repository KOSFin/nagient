# Developer Guide

English · [Русская версия](README.ru.md) · [All documentation](../README.md)

Nagient has two extension runtimes: Python plugins expose `build_plugin()`, while process plugins exchange one JSON request and response over stdin/stdout. Both use the same manifests and discovery model.

## Choose A Development Path

| Goal | Start here |
| --- | --- |
| Build a new plugin | [Plugin development guide](../PLUGIN_DEVELOPMENT.md) |
| Start from a clean repository | [Official plugin template](https://github.com/KOSFin/nagient-plugin-template) |
| Implement a runtime adapter | [Plugin contracts](../plugin-contracts.md) |
| Understand ownership and discovery | [Architecture](../architecture.md) |
| Prepare a contribution | [Testing and CI](testing.md) |

## Development Contents

| Article | What it covers |
| --- | --- |
| [Build your first plugin](../PLUGIN_DEVELOPMENT.md) | Repository layout, manifests, fields, dependencies, validation, and publishing. |
| [Plugin contracts](../plugin-contracts.md) | Transport, provider, tool, Python, and process protocols. |
| [Architecture](../architecture.md) | Core boundaries, dependency policy, runtime flow, security, and state. |
| [Testing and CI](testing.md) | Unit, integration, smoke, lint, and release checks. |
| [Contribution guide](../../CONTRIBUTING.md) | Local setup, code style, commits, and pull requests. |

Keep network SDKs and native dependencies in the plugin repository. The core package deliberately retains only console, webhook, providers, and system tools required for a useful first run.
