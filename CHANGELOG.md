# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.4] - 2026-07-15

### Added

- **Git Integration:** Added `workspace.git.clone()` for cloning repositories
- **Git Integration:** Added `workspace.git.push()` for pushing commits to remotes
- **Git Integration:** Added `workspace.git.pull()` for pulling changes from remotes
- **Documentation:** Added `CONTRIBUTING.md` with contribution guidelines
- **Documentation:** Added `SECURITY.md` with security policy and best practices
- **Documentation:** Added `docs/PLUGIN_DEVELOPMENT.md` - comprehensive plugin development guide
- **Documentation:** Added `.claude/` directory with project analysis and development docs
- **Tests:** Added unit tests for bundled transport plugins (`tests/unit/test_bundled_transports.py`)
- **Tests:** Added unit tests for plugin registry (`tests/unit/test_plugin_registry.py`)

### Changed

- **BREAKING:** Refactored bundled transports to use manifest-driven plugin system
  - Moved `TelegramTransportPlugin` from `plugins/builtin.py` to `bundled_transports/telegram/transport.py`
  - Moved `ConsoleTransportPlugin` from `plugins/builtin.py` to `bundled_transports/console/transport.py`
  - Moved `WebhookTransportPlugin` from `plugins/builtin.py` to `bundled_transports/webhook/transport.py`
  - All bundled transports now load through standard plugin discovery
  - `plugins/builtin.py` simplified to compatibility stub

### Fixed

- Git operations now properly handle clone, push, and pull with credentials
- Plugin loading is now consistent between bundled and user plugins
- Improved error messages for Git authentication failures

### Improved

- **Architecture:** Manifest-driven plugin system is now fully consistent
- **Documentation:** Comprehensive guides for contributors and plugin developers
- **Security:** Documented security best practices and vulnerability reporting process
- **Developer Experience:** Bundled plugins serve as reference implementations

## [0.8.3] - 2024-06-09

### Added

- Direct scheduled actions and progress broadcasts
- Agent progress setup menu

### Changed

- Made transport and plugin contracts manifest-driven

### Fixed

- Lint issues

## [0.1.0] - 2024-04-26

### Added

- Initial release
- Basic agent runtime
- Transport plugin framework
- Provider plugin framework
- Tool plugin framework
- Docker support
- CLI interface

[0.8.4]: https://github.com/YOUR_ORG/nagient/compare/v0.8.3...v0.8.4
[0.8.3]: https://github.com/YOUR_ORG/nagient/compare/v0.1.0...v0.8.3
[0.1.0]: https://github.com/YOUR_ORG/nagient/releases/tag/v0.1.0
