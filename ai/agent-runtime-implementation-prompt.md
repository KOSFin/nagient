# Implementation Prompt For Next AI Agent

Language: English | [Русский](agent-runtime-implementation-prompt.ru.md)

This file is the English companion to the Russian implementation prompt.

## Scope

You work in the `Nagient` repository and continue implementation of the next major runtime layer on top of the existing platform and delivery foundation.

Your work must preserve existing contracts while introducing runtime capabilities (agent loop, workspace controls, tools, secure interactions, approvals, backups, and memory state).

## Required Reading Before Changes

- [ai/README.md](README.md)
- [ai/README.ru.md](README.ru.md)
- [docs/architecture.md](../docs/architecture.md)
- [docs/architecture.ru.md](../docs/architecture.ru.md)
- [README.md](../README.md)
- [README.ru.md](../README.ru.md)
- `src/nagient/app/settings.py`
- `src/nagient/app/configuration.py`
- `src/nagient/app/container.py`
- `src/nagient/infrastructure/runtime.py`
- `src/nagient/plugins/`
- `src/nagient/providers/`
- `src/nagient/application/services/`
- `src/nagient/cli.py`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

## Non-Breaking Rules

Do not break these invariants without synchronized updates across code, scripts, and tests:

- update center contract
- tag-driven delivery flow
- centralized update resolution
- bootstrap/reconcile activation contract
- transport/provider/tool/workspace/security contracts

## Implementation Standards

- study existing code and tests before design changes
- design before implementation
- add tests for each new behavioral contract
- update docs after code and tests are stable
- keep boundaries explicit (application/domain/infrastructure)

## Quality Gate

Before completion, ensure:

- implementation is complete and coherent
- tests are added and passing
- CI coverage includes new paths
- documentation is synchronized with behavior
- secret handling remains redacted in agent-visible output
- high-risk actions remain approval-gated

## Canonical Version

The full canonical implementation task is maintained in Russian in:

- [agent-runtime-implementation-prompt.ru.md](agent-runtime-implementation-prompt.ru.md)
