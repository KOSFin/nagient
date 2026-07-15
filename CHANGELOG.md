# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.8.7]: https://github.com/KOSFin/nagient/compare/v0.8.6...v0.8.7
[0.8.6]: https://github.com/KOSFin/nagient/compare/v0.8.5...v0.8.6
[0.8.5]: https://github.com/KOSFin/nagient/compare/v0.8.4...v0.8.5
[0.8.3]: https://github.com/KOSFin/nagient/compare/v0.1.0...v0.8.3
[0.1.0]: https://github.com/KOSFin/nagient/releases/tag/v0.1.0
