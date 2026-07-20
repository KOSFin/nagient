# Developer Guide

Language: English | [Русский](README.ru.md)

This section is for people building providers, transports, tools, and runtime
integrations. Start with the contract, then choose Python or a process plugin.

## Paths

- [Plugin development](../PLUGIN_DEVELOPMENT.md)
- [Plugin contracts](../plugin-contracts.md)
- [Plugin template and repository layout](../PLUGIN_DEVELOPMENT.md#template-repository)
- [Architecture and dependency policy](../architecture.md)
- [Testing and CI](testing.md)

## Supported implementation languages

- Python 3.11+ modules using `build_plugin()`.
- Any language that can read/write one JSON request/response over stdin/stdout
  using `runtime = "process"` and `protocol = "nagient.process.v1"`.

Keep network SDKs and native dependencies in the plugin. The core remains a
small, cross-platform Python package.
