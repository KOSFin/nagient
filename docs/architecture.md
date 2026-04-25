# Architecture Notes

Nagient is split into a narrow control surface and a centralized release/update model.

## Layers

- `nagient.app` wires settings and service objects.
- `nagient.application.services` contains use-cases such as health checks and update discovery.
- `nagient.domain` owns release entities and semantic version comparison.
- `nagient.infrastructure` handles manifests, registry loading, runtime heartbeat writing, and file transport.
- `nagient.migrations` plans ordered upgrade steps from release metadata.

## Bootstrap And Activation

Runtime activation now follows a single pipeline regardless of whether the user starts through local CLI, `curl | sh`, PowerShell, Docker image, or Docker Compose:

1. Assemble config from `config.toml`, environment defaults, and `secrets.env`.
2. Discover built-in and custom Python transport plugins from `plugins/`.
3. Run `preflight` checks: config lint, secret reference validation, plugin self-tests, transport health checks.
4. Run `reconcile` to persist `activation-report.json`, `effective-config.json`, and `last-known-good.json`.
5. Start the runtime loop only when the activation report is allowed by safe mode.

Safe mode is enabled by default. When it is disabled, the runtime may still start in a degraded state.

## Transport Plugin Contract

Transport plugins are Python components with:

- `plugin.toml` for manifest metadata and function bindings
- `transport.py` with the plugin implementation
- `instructions.md` for the agent-facing transport usage contract
- optional `schema.json` for plugin-local config schema

Every transport plugin must declare slot bindings for:

- `send_message`
- `send_notification`
- `normalize_inbound_event`
- `healthcheck`
- `selftest`
- `start`
- `stop`

Plugins may also declare custom namespaced functions such as `telegram.showPopup` or `webhook.replyJson`.

## Update Center Contract

The update center has two primary JSON documents:

1. `channels/<channel>.json` points to the latest release manifest for a channel.
2. `manifests/<version>.json` describes Docker image, installers, deployment assets, migration steps, and release notices.

This contract is the shared source for shell installers, PowerShell installers, the CLI, and any future notification channel.

## Delivery Model

Tagging `vX.Y.Z` should produce:

1. A Python distribution in `dist/`.
2. A Docker image `docker.io/<namespace>/<image>:X.Y.Z`.
3. Versioned installer assets under `<update-base-url>/X.Y.Z/`.
4. A release manifest under `<update-base-url>/manifests/X.Y.Z.json`.
5. A channel pointer under `<update-base-url>/channels/stable.json`.
