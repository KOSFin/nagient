# Plugin Development Guide

This guide teaches you how to create custom plugins for Nagient using the manifest-driven plugin system.

## Table of Contents

1. [Plugin System Overview](#plugin-system-overview)
2. [Transport Plugins](#transport-plugins)
3. [Tool Plugins](#tool-plugins)
4. [Provider Plugins](#provider-plugins)
5. [Best Practices](#best-practices)
6. [Testing](#testing)
7. [Examples](#examples)

## Plugin System Overview

### Architecture

Nagient uses a **manifest-driven plugin system**:

1. **Manifest File:** Declares plugin metadata, configuration, and functions
2. **Implementation File:** Contains the plugin code
3. **Discovery:** Plugin registry discovers plugins from directories
4. **Loading:** Registry loads plugin manifest and instantiates implementation
5. **Execution:** Runtime calls plugin functions through the registry

### Key Principles

- **Manifest-Driven:** All plugins load via `plugin.toml` or `tool.toml` manifests
- **Factory Pattern:** Plugins export `build_plugin()` factory function
- **Discovery-Based:** No manual registration, automatic discovery from directories
- **Consistent Loading:** Bundled and user plugins load identically

### Plugin Types

- **Transport Plugins:** Handle message delivery (Telegram, Slack, email, etc.)
- **Tool Plugins:** Provide agent capabilities (GitHub API, Jira, databases, etc.)
- **Provider Plugins:** Connect to LLM providers (OpenAI, Anthropic, etc.)

### Plugin dependencies

Dependencies are isolated per plugin and are never installed into Nagient's
main environment:

```toml
runtime = "python"
dependencies = ["aiogram>=3,<4", "aiohttp>=3.9"]
requirements_file = "requirements.txt" # optional
```

`nagient plugin install` creates `<plugin-directory>/.venv` and installs these
packages automatically. In Docker, the environment lives in the persistent
`data` directory and is reused after container restarts. Use
`--upgrade-dependencies` to refresh packages or `--no-dependencies` only for
offline staging. Python process entrypoints use the same plugin environment.

### aiogram reference plugin

The repository includes `examples/plugins/telegram-aiogram`. Copy it into a
separate Git repository, publish it, and install it by URL. It follows the same
transport contract as `builtin.telegram`, while keeping `aiogram` inside the
plugin's private environment. Configure `bot_token_secret` and optionally
`proxy_url` after installation.

## Transport Plugins

Transport plugins enable the agent to send and receive messages through various channels.

### Directory Structure

```
~/.nagient/plugins/my-transport/
├── plugin.toml          # Manifest
├── transport.py         # Implementation
├── instructions.md      # Agent instructions
├── schema.json          # Optional JSON schema
└── README.md            # Documentation
```

### Manifest: `plugin.toml`

```toml
# Required fields
id = "custom.my-transport"
type = "transport"
version = "0.1.0"
display_name = "My Transport"
namespace = "mytransport"
runtime = "python"
entrypoint = "transport.py"
instructions_file = "instructions.md"

# Optional configuration schema
config_schema_file = "schema.json"

# Configuration keys
required_config = ["api_key_secret"]
optional_config = ["timeout_seconds", "base_url"]
secret_config = ["api_key_secret"]

# Custom functions beyond required slots
custom_functions = [
  "mytransport.sendTyping",
  "mytransport.editMessage",
]

# Required transport slots
[required_slots]
send_message = "mytransport.sendMessage"
send_notification = "mytransport.sendNotification"
normalize_inbound_event = "mytransport.normalizeInboundEvent"
poll_inbound_events = "mytransport.pollInboundEvents"
healthcheck = "mytransport.healthcheck"
selftest = "mytransport.selftest"
start = "mytransport.start"
stop = "mytransport.stop"

# Function bindings (exposed name -> method name)
[function_bindings]
"mytransport.sendMessage" = "send_message"
"mytransport.sendNotification" = "send_notification"
"mytransport.normalizeInboundEvent" = "normalize_inbound_event"
"mytransport.pollInboundEvents" = "poll_inbound_events"
"mytransport.healthcheck" = "healthcheck"
"mytransport.selftest" = "self_test"
"mytransport.start" = "start"
"mytransport.stop" = "stop"
"mytransport.sendTyping" = "send_typing"
"mytransport.editMessage" = "edit_message"

# Optional: Configuration field metadata
[[config_fields]]
key = "api_key_secret"
label = "API Key"
help_text = "Secret name storing the API key for this transport."
value_type = "secret"
category = "connection"
required = true
secret = true

[[config_fields]]
key = "timeout_seconds"
label = "Request Timeout"
help_text = "HTTP request timeout in seconds."
value_type = "integer"
category = "advanced"
```

### Implementation: `transport.py`

```python
from __future__ import annotations

from collections.abc import Mapping

from nagient.domain.entities.system_state import CheckIssue
from nagient.plugins.base import BaseTransportPlugin, TransportRuntimeContext


class MyTransportPlugin(BaseTransportPlugin):
    """My custom transport implementation."""

    def __init__(self) -> None:
        # Initialize any state needed
        self._runtime_contexts: dict[str, TransportRuntimeContext] = {}

    def validate_config(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        """Validate configuration and secrets."""
        issues: list[CheckIssue] = []
        
        # Check required secret
        api_key_secret = config.get("api_key_secret")
        if not isinstance(api_key_secret, str):
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.my_transport.missing_secret",
                    message=f"Transport {transport_id!r} requires api_key_secret.",
                    source=transport_id,
                )
            )
        elif api_key_secret not in secrets:
            issues.append(
                CheckIssue(
                    severity="error",
                    code="transport.my_transport.secret_not_found",
                    message=f"Transport {transport_id!r} cannot find secret {api_key_secret!r}.",
                    source=transport_id,
                    hint="Add the secret to secrets.env or tool-secrets.env.",
                )
            )
        
        return issues

    def bind_runtime(
        self,
        transport_id: str,
        runtime: TransportRuntimeContext,
    ) -> None:
        """Bind runtime context for logging and state management."""
        self._runtime_contexts[transport_id] = runtime

    def start(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> None:
        """Called when transport is activated."""
        # Initialize connections, load state, etc.
        pass

    def stop(self, transport_id: str) -> None:
        """Called when transport is deactivated."""
        # Clean up connections, save state, etc.
        pass

    def send_message(self, payload: dict[str, object]) -> dict[str, object]:
        """Send a message through this transport."""
        # Extract message details from payload
        text = str(payload.get("text", ""))
        target = payload.get("_target")  # Reply target from inbound event
        
        # Send message via your API
        # ...
        
        return {
            "status": "sent",
            "message_id": "unique-message-id",
        }

    def send_notification(self, payload: dict[str, object]) -> dict[str, object]:
        """Send a notification (usually with muted/silent flag)."""
        notification_payload = dict(payload)
        notification_payload.setdefault("silent", True)
        return self.send_message(notification_payload)

    def normalize_inbound_event(self, payload: object) -> dict[str, object]:
        """
        Normalize an inbound event to standard format.
        
        Returns:
            {
                "kind": "my_transport",
                "event_type": "message" | "command" | "callback" | etc,
                "session_id": "unique-session-id",
                "text": "message text",
                "reply_target": {"key": "value"},  # Used for sending replies
                "payload": {...},  # Original payload
            }
        """
        if not isinstance(payload, dict):
            return {"kind": "my_transport", "event_type": "unknown", "payload": payload}
        
        return {
            "kind": "my_transport",
            "event_type": "message",
            "session_id": f"my_transport:{payload.get('user_id')}",
            "text": str(payload.get("text", "")),
            "reply_target": {"user_id": payload.get("user_id")},
            "payload": dict(payload),
        }

    def poll_inbound_events(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[object]:
        """
        Poll for new inbound events.
        
        Returns list of raw events that will be passed to normalize_inbound_event.
        """
        # Poll your API for new messages
        # Return list of raw event objects
        return []

    def healthcheck(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        """
        Check if transport is healthy and ready.
        
        Returns list of issues (empty if healthy).
        """
        return []

    def self_test(
        self,
        transport_id: str,
        config: Mapping[str, object],
        secrets: Mapping[str, str],
    ) -> list[CheckIssue]:
        """
        Run self-tests on configuration and connectivity.
        
        More thorough than healthcheck.
        """
        return []

    # Optional: Custom functions
    def send_typing(self, payload: dict[str, object]) -> dict[str, object]:
        """Send typing indicator."""
        return {"status": "sent"}

    def edit_message(self, payload: dict[str, object]) -> dict[str, object]:
        """Edit a previously sent message."""
        return {"status": "edited"}


def build_plugin() -> MyTransportPlugin:
    """Factory function required by plugin system."""
    return MyTransportPlugin()
```

### Instructions: `instructions.md`

```markdown
Use mytransport.sendMessage to send messages to users.
Use mytransport.sendNotification for system notifications.
Use mytransport.sendTyping to show typing indicators.

The my-transport transport supports markdown formatting.
```

### Testing Your Transport

```python
# Test loading
from pathlib import Path
from nagient.plugins.registry import TransportPluginRegistry

registry = TransportPluginRegistry()
discovery = registry.discover(Path("~/.nagient/plugins"))

# Check if your plugin loaded
plugin = discovery.plugins.get("custom.my-transport")
assert plugin is not None

# Test instantiation
instance = plugin.implementation
assert instance is not None

# Test validation
issues = instance.validate_config(
    "test",
    {"api_key_secret": "TEST_KEY"},
    {"TEST_KEY": "test-value"}
)
assert not issues
```

## Tool Plugins

Tool plugins provide agent capabilities like API integrations, database access, etc.

### Directory Structure

```
~/.nagient/tools/my-tool/
├── tool.toml           # Manifest
├── tool.py             # Implementation
└── README.md           # Documentation
```

### Manifest: `tool.toml`

```toml
id = "custom.my-tool"
type = "tool"
version = "0.1.0"
display_name = "My Tool"
namespace = "mytool"
runtime = "python"
entrypoint = "tool.py"
capabilities = ["api", "external"]

# Configuration
optional_config = ["api_key_secret", "base_url"]

# Functions this tool provides
[[functions]]
name = "mytool.get_data"
binding = "get_data"
description = "Fetch data from the API"
permissions = ["mytool.read"]
secret_bindings = ["api_key_secret"]
input_schema = { type = "object" }
output_schema = { type = "object" }

[[functions]]
name = "mytool.create_item"
binding = "create_item"
description = "Create a new item via the API"
permissions = ["mytool.write"]
secret_bindings = ["api_key_secret"]
side_effect = "external"
approval_policy = "required"
dry_run_supported = true
input_schema = { type = "object" }
output_schema = { type = "object" }
```

### Implementation: `tool.py`

```python
from __future__ import annotations

from collections.abc import Mapping

from nagient.domain.entities.system_state import CheckIssue
from nagient.tools.base import BaseToolPlugin, ToolExecutionContext


class MyToolPlugin(BaseToolPlugin):
    """My custom tool implementation."""

    def validate_config(
        self,
        tool_id: str,
        config: Mapping[str, object],
        secret_broker: object,
    ) -> list[CheckIssue]:
        """Validate tool configuration."""
        # Similar to transport validation
        return []

    def get_data(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        """Fetch data from the API."""
        # Get API key from secret broker
        api_key = context.secret_broker.resolve_secret("MY_TOOL_API_KEY", scope_hint="tool")
        
        # Extract arguments
        query = str(arguments.get("query", ""))
        
        # Call your API
        # ...
        
        return {
            "status": "success",
            "data": [...],
        }

    def create_item(
        self,
        arguments: Mapping[str, object],
        context: ToolExecutionContext,
    ) -> dict[str, object]:
        """Create an item via the API."""
        if context.dry_run:
            return {"status": "dry_run", "would_create": arguments}
        
        # Call your API
        # ...
        
        return {
            "status": "created",
            "item_id": "new-id",
        }


def build_plugin() -> MyToolPlugin:
    return MyToolPlugin()
```

## Best Practices

### Security

1. **Never log secrets** - Use secret broker, never print/log API keys
2. **Validate input** - Always validate and sanitize user input
3. **Declare permissions** - Accurately declare required permissions
4. **Approval policies** - Set appropriate policies for risky operations

### Error Handling

```python
def send_message(self, payload):
    try:
        # Your code
        pass
    except SomeAPIError as exc:
        # Re-raise with user-friendly message
        raise ValueError(f"Failed to send message: {exc}") from exc
```

### Configuration

```python
def _get_timeout(self, config: Mapping[str, object]) -> int:
    """Extract timeout with validation and default."""
    value = config.get("timeout_seconds", 30)
    if isinstance(value, int) and value > 0:
        return value
    return 30
```

### State Management

```python
def _load_state(self, transport_id: str) -> None:
    runtime = self._runtime_contexts.get(transport_id)
    if runtime is None:
        return
    state_path = runtime.state_dir / "my-state.json"
    if state_path.exists():
        # Load state
        pass
```

## Testing

### Unit Tests

```python
def test_plugin_loads():
    from my_plugin.tool import build_plugin
    plugin = build_plugin()
    assert plugin is not None
```

### Integration Tests

```python
def test_send_message():
    plugin = build_plugin()
    result = plugin.send_message({"text": "test"})
    assert result["status"] == "sent"
```

## Examples

### Study Bundled Plugins

**Telegram Transport** (Full-featured):
- Location: `src/nagient/bundled_transports/telegram/`
- Features: HTTP client, proxy, state management, message chunking
- ~680 lines, production-ready

**Console Transport** (Minimal):
- Location: `src/nagient/bundled_transports/console/`
- Features: Basic message queuing
- ~55 lines, simple example

**GitHub API Tool**:
- Location: `src/nagient/bundled_tools/github_api/`
- Features: REST API integration, authentication
- Great example of tool plugin

### Community Plugins

(Add links to community plugins here)

## Troubleshooting

### Plugin Not Loading

1. Check `nagient transport list` or `nagient tool list`
2. Check for errors: `nagient doctor`
3. Validate manifest syntax
4. Ensure `build_plugin()` exists and returns correct type

### Configuration Errors

1. Run `nagient preflight` to validate config
2. Check secrets are defined in `secrets.env` or `tool-secrets.env`
3. Verify field names match manifest

### Import Errors

Make sure your plugin doesn't import Nagient internals except:
- `nagient.plugins.base` (for transports)
- `nagient.tools.base` (for tools)
- `nagient.domain.entities.*` (for types)

## Resources

- **Architecture:** [docs/architecture.md](../docs/architecture.md)
- **API Reference:** Inline docstrings in base classes
- **Examples:** Bundled plugins in `src/nagient/bundled_*/`
- **Issues:** [GitHub Issues](https://github.com/YOUR_ORG/nagient/issues)

---

*Happy plugin development!*
