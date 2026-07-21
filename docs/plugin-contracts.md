# Plugin Contracts

Nagient extensions are runtime components discovered from manifest directories. Bundled
extensions use the same discovery path as user extensions.

Every manifest may declare isolated dependencies:

```toml
dependencies = ["package>=1,<2"]
requirements_file = "requirements.txt"
```

The installer creates `.venv` inside the plugin directory and uses it for both
Python imports and Python process entrypoints. The main Nagient environment is
not modified.

## Transport plugins

Transport plugins live in a directory with:

- `plugin.toml`
- an entrypoint named by `entrypoint`
- `instructions.md`
- an optional `schema.json`

Required transport slots are stable:

- `send_message`
- `send_notification`
- `normalize_inbound_event`
- `poll_inbound_events`
- `healthcheck`
- `selftest`
- `start`
- `stop`

The runtime always attaches generic payload metadata to outbound calls:

- `_transport_config`: the configured profile values
- `_transport_id`: the configured transport instance id
- `_transport_secrets`: scoped secrets resolved from config values whose keys look like
  secret references

Plugins should read secrets from `_transport_secrets`; they should not rely on
transport-specific runtime fields.

Transport manifests may declare default targeting metadata:

```toml
default_target_field = "chat_id"
default_target_config_key = "default_chat_id"
default_target_always_available = false
send_message_hint = "Optional custom hint shown to the agent and CLI."
```

If this metadata is present, the router can describe custom transports without hardcoding
plugin ids.

### Interaction capabilities

Declare optional user-experience features instead of making the core test a transport
name. `interaction_capabilities` tells the runtime what it may offer; the paired
`interaction_functions` table maps a capability to an exposed function:

```toml
interaction_capabilities = ["approval.inline", "approval.callback", "activity.typing"]

[interaction_functions]
"approval.callback.answer" = "vendor.answerCallback"
"approval.callback.edit" = "vendor.editMessage"
"activity.typing" = "vendor.sendTyping"
```

The core falls back to a textual approval when `approval.inline` is absent. A transport
that supports native drafts can declare `stream.draft`; the core may use it for live
delivery and must still send a final durable message. Plugins own API-specific limits,
throttling, media, and rendering.

## Tool plugins

Tool plugins live in a directory with:

- `tool.toml`
- an entrypoint named by `entrypoint`
- an optional `schema.json`

Each `[[functions]]` entry declares the public function name, binding, schemas,
permissions, side effect class, approval policy, and whether a user-expected action may
be auto-approved:

```toml
[[functions]]
name = "vendor.deploy.run"
binding = "deploy"
description = "Deploy the selected target."
permissions = ["vendor.deploy"]
side_effect = "external"
approval_policy = "required"
auto_approve_when_expected = true
dry_run_supported = true
```

Use `auto_approve_when_expected` only for actions where the user explicitly requesting
the exact operation is enough to skip a second approval prompt.

## Log channels

Transport, provider, and tool manifests may declare log channels:

```toml
[[log_channels]]
name = "transport.telegram"
description = "Telegram polling and outbound Bot API delivery."
default_level = "info"
```

Runtime config can override component log levels:

```toml
[agent.logging.components]
"transport.telegram" = "debug"
"tool.github.api" = "warning"
```

If a plugin declares no log channels, the platform treats it as silent by default except
for core runtime errors.
