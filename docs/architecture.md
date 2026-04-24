# Architecture Notes

Nagient is split into a narrow control surface and a centralized release/update model.

## Layers

- `nagient.app` wires settings and service objects.
- `nagient.application.services` contains use-cases such as health checks and update discovery.
- `nagient.domain` owns release entities and semantic version comparison.
- `nagient.infrastructure` handles manifests, registry loading, runtime heartbeat writing, and file transport.
- `nagient.migrations` plans ordered upgrade steps from release metadata.

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

