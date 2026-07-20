# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.10] - 2026-07-20

### Added

- Docker-free local runtime installers for Bash and PowerShell using a Python
  virtual environment and a small process launcher.
- Source-checkout smoke coverage for the local installer.

## [0.9.9] - 2026-07-20

### Fixed

- Catalog installation now passes each entry's pinned Git tag to the installer.

## [0.9.8] - 2026-07-20

### Added

- Published `nagient.telegram`, `nagient.github_api`, and
  `nagient-plugin-template` repositories and pinned them in the official catalog.

## [0.9.7] - 2026-07-20

### Added

- Reviewed plugin catalog with compact `nagient plugin catalog list|install` commands
  and a published JSON manifest under `metadata/plugins/`.
- Telegram chat, sender, and chat-type allowlists plus a `telegram.streamMessage`
  primitive for progressively editing one reply message.
- English and Russian plugin operations documentation, including the environment
  naming contract for plugin-owned fields.

### Changed

- Git plugin install and removal failures now return concise CLI errors and exit code 2
  instead of exposing a Python traceback to operators.

## [0.9.6] - 2026-07-18

### Fixed

- The generated Docker Compose deployment persists the complete Nagient
  runtime under one `./data:/opt/nagient` mount, preventing missing-directory
  failures caused by separate nested bind mounts.

## [0.9.5] - 2026-07-18

### Fixed

- Runtime startup creates the parent directory for the heartbeat file before
  writing it.
- Runtime logging creates only the configured log directory instead of
  attempting to create the log file as a directory.

## [0.9.4] - 2026-07-18

### Changed

- The first provider configured with real settings is enabled automatically when
  no provider is active.
- The first active provider is selected as the default only when no default was
  chosen manually.
- Explicit `--enable`, `--disable`, `--default`, and `--not-default` flags retain
  priority over automatic selection.

## [0.9.3] - 2026-07-18

### Added

- Isolated per-plugin Python dependencies installed into `<plugin>/.venv`.
- `dependencies` and `requirements_file` manifest fields for transport, provider,
  and tool plugins.
- `--no-dependencies` and `--upgrade-dependencies` plugin installation flags.
- Reference `aiogram` Telegram transport with HTTP, HTTPS, and SOCKS proxy support.
- Russian and English plugin dependency documentation.

### Changed

- Python plugins and Python process entrypoints use their private dependency environment.
- Built-in Telegram remains available as a dependency-free fallback.

## [0.9.2] - 2026-07-18

### Added

- Unified `nagient plugin install|list|remove` commands for Git-based transport,
  provider, and tool plugins.
- `NAGIENT_PLUGIN_SPECS` for idempotent plugin installation from Docker Compose.
- Russian deployment, environment, plugin-development, and secret templates.

### Changed

- Docker documentation now explains the difference between pulling an image and
  running a persistent Compose deployment.
- Compose restarts preserve installed plugin sources and do not clone them again.

## [0.9.1] - 2026-07-16

### Added

- Complete env-only Docker Compose deployment: provider, transport, agent, tool,
  workspace, and secret settings can be supplied through `.env` without running
  the Nagient CLI or editing generated TOML/secret files.
- `NAGIENT_CONFIG_JSON`, `NAGIENT_SECRETS_JSON`, and
  `NAGIENT_TOOL_SECRETS_JSON` for complete and future-compatible environment
  configuration, including arbitrary plugin fields and secret names.
- A safe-by-default webhook port mapping, bound to `127.0.0.1` unless explicitly
  exposed through `NAGIENT_WEBHOOK_BIND_ADDRESS`.

### Changed

- Environment values take precedence over persisted configuration and secrets.
- Server deployment documentation now uses one `.env` plus
  `docker compose up -d` as the primary installation path.

## [0.9.0] - 2026-07-15

### Added

- Ready-to-run `docker-compose.yml` and `.env.example` at the repository root
  for self-hosted deployment without the hosted installer. A single `./data`
  mount holds config, secrets, state, and logs; the container seeds
  `config.toml` and `secrets.env` on first run, so no host files must exist
  beforehand.
- `docs/deploy.md` and `docs/deploy.ru.md` — step-by-step guide for deploying
  Nagient on a server with Docker Compose, including provider/transport setup,
  updates, backups, and troubleshooting.

### Fixed

- Agent no longer stops mid-plan on multi-step tasks. When the runtime reaches
  `max_turns` with tool calls still pending, it now makes one bounded
  summary-only provider call to compose a real answer from the tool results
  already gathered, instead of returning the last intermediate planning message.

### Changed

- Default `agent.max_turns` raised from 4 to 12 so multi-step tool workflows
  (sequential API calls, multi-file edits) can complete within the loop.
- The provider prompt now instructs the model to batch independent tool calls
  in a single turn instead of emitting one tool call per turn, reducing the
  number of round-trips a task needs.

## [0.8.7] - 2026-07-15

### Fixed

- Updater assets are now replaced atomically through temporary files, preventing
  `nagient-update` from corrupting its own running script during self-update.

## [0.8.6] - 2026-07-15

### Fixed

- Update metadata now advances to the target release only after Docker pull and
  restart complete successfully, so a failed update can be retried instead of
  reporting the target version as already installed.

## [0.8.5] - 2026-07-15

### Added

- `workspace.git.clone` — clone a remote repository into the workspace using the
  configured git identity and credentials.
- `workspace.git.push` — push commits to a remote with credential support.
- `workspace.git.pull` — pull changes from a remote with credential support.
- `CONTRIBUTING.md` — contribution workflow, commit conventions, and quality gates.
- `SECURITY.md` — security policy, reporting process, and secret-handling guidance.
- `docs/PLUGIN_DEVELOPMENT.md` — end-to-end guide for authoring transport, provider,
  and tool plugins.
- Unit tests for the bundled transport plugins and the transport plugin registry.

### Changed

- Bundled transports now load exclusively through the manifest-driven plugin
  discovery path, identical to user-authored plugins:
  - `TelegramTransportPlugin` now lives in `bundled_transports/telegram/transport.py`.
  - `ConsoleTransportPlugin` now lives in `bundled_transports/console/transport.py`.
  - `WebhookTransportPlugin` now lives in `bundled_transports/webhook/transport.py`.
  - `plugins/builtin.py` no longer ships hardcoded transport implementations.

### Fixed

- Git authentication failures now surface clearer, redacted error messages.
- Plugin loading behaves consistently for bundled and user plugins.

## [0.8.3] - 2026-06-09

### Added

- Direct scheduled actions and progress broadcasts.
- Agent progress setup menu.

### Changed

- Made transport and plugin contracts manifest-driven.

## [0.1.0] - 2026-04-26

### Added

- Initial release: agent runtime, transport/provider/tool plugin frameworks,
  Docker support, and CLI interface.

[0.9.1]: https://github.com/KOSFin/nagient/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/KOSFin/nagient/compare/v0.8.7...v0.9.0
[0.8.7]: https://github.com/KOSFin/nagient/compare/v0.8.6...v0.8.7
[0.8.6]: https://github.com/KOSFin/nagient/compare/v0.8.5...v0.8.6
[0.8.5]: https://github.com/KOSFin/nagient/compare/v0.8.4...v0.8.5
[0.8.3]: https://github.com/KOSFin/nagient/compare/v0.1.0...v0.8.3
[0.1.0]: https://github.com/KOSFin/nagient/releases/tag/v0.1.0
