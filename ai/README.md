# AI Project Context

Language: English | [Русский](README.ru.md)

This document is for AI agents and automation workflows that continue development of Nagient.

## 1. Project Intent

Nagient is designed as an agent platform with delivery and update contracts first, and runtime intelligence layered on top.

Platform goals:

- install through Docker image
- install through shell script
- install through PowerShell script
- publish releases automatically
- manage updates centrally
- keep migrations in the release model
- support future update notifications beyond CLI

## 2. Current Scope

Implemented foundation:

- Python package with CLI entrypoints
- split between app/application/domain/infrastructure
- bootstrap and reconcile cycle for runtime activation
- transport plugin framework and registry
- provider plugin framework and auth workflows
- tool plugin framework and built-in workspace tools
- workspace layout manager and path guards
- backup and checkpoint management
- secret broker with redaction boundaries
- secure interaction and approval workflow stores
- structured agent turn contract and executor
- release metadata generation and update center flow
- CI, release automation, and smoke/integration/unit tests

Important: the repository is still a platform scaffold, not a fully autonomous agent runtime.

## 3. Repository Map

Core references:

- `src/nagient/cli.py`
- `src/nagient/app/settings.py`
- `src/nagient/app/configuration.py`
- `src/nagient/app/container.py`
- `src/nagient/application/services/`
- `src/nagient/infrastructure/`
- `src/nagient/plugins/`
- `src/nagient/providers/`
- `src/nagient/tools/`
- `src/nagient/workspace/`
- `src/nagient/security/`
- `src/nagient/migrations/`

Bundled extensions (manifest-driven, loaded exactly like user plugins):

- `src/nagient/bundled_transports/telegram/`
- `src/nagient/bundled_transports/console/`
- `src/nagient/bundled_transports/webhook/`
- `src/nagient/bundled_tools/github_api/`

## 3a. Plugin Architecture Convention (Important)

Bundled transports and tools are NOT special-cased. Each one is a self-contained
directory with a `plugin.toml`/`tool.toml` manifest and an `entrypoint` module that
exports `build_plugin()`. The registries in `src/nagient/plugins/registry.py` and
`src/nagient/tools/registry.py` discover the bundled directories first, then the
user plugin/tool directories, using the same code path.

Rules to preserve:

- Do not reintroduce hardcoded transport/tool classes into `plugins/builtin.py`
  or a central registry. `plugins/builtin.py` is only a thin compatibility stub.
- A new bundled transport is added as a new directory under `bundled_transports/`
  with a manifest and a `transport.py` exposing `build_plugin()`.
- Bundled plugins double as reference implementations for users writing their own,
  so keep them clean and idiomatic.

Delivery references:

- `scripts/install.sh`, `scripts/install.ps1`
- `scripts/update.sh`, `scripts/update.ps1`
- `scripts/uninstall.sh`, `scripts/uninstall.ps1`
- `scripts/release/`
- `metadata/update-center/`
- `.github/workflows/`

## 4. Contracts That Must Stay Stable

- update center contract: `channels/<channel>.json` and `manifests/<version>.json`
- tag-driven release flow: `vX.Y.Z`
- centralized update resolution by manifests, not installer-local version logic
- bootstrap/reconcile flow and safe-mode semantics
- transport/provider/tool/workspace/security boundaries

If one contract changes, update code, scripts, and tests together.

## 5. CLI Surface (Current)

- `nagient init|status|doctor|preflight|reconcile|serve`
- `nagient transport list|scaffold`
- `nagient provider list|scaffold|models`
- `nagient auth status|login|complete|logout`
- `nagient tool list|scaffold|invoke`
- `nagient interaction list|submit`
- `nagient approval list|respond`
- `nagient update check`
- `nagient manifest render`
- `nagient migrations plan`
- `nagient agent turn --request-file ...`

## 6. Testing Focus

Regression coverage should always include:

- update metadata parsing and serialization
- settings/config loading and path handling
- preflight/reconcile behavior in safe mode
- plugin registries and scaffold generators
- secret broker redaction guarantees
- workspace safety checks
- release script contracts and smoke checks

## 7. Recommended Next Steps

1. Implement persistent runtime state model.
2. Add provider abstraction for model execution.
3. Build task loop and scheduling semantics.
4. Expand secure tool runtime and approval gates.
5. Add external surfaces (API, webhooks, richer UX).

## 8. Working Prompt

Main implementation prompt files:

- Russian: [agent-runtime-implementation-prompt.ru.md](agent-runtime-implementation-prompt.ru.md)
- English: [agent-runtime-implementation-prompt.md](agent-runtime-implementation-prompt.md)
