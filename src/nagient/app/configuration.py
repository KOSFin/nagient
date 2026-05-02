from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nagient.app.settings import Settings


@dataclass(frozen=True)
class TransportInstanceConfig:
    transport_id: str
    plugin_id: str
    enabled: bool
    config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "transport_id": self.transport_id,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "config": dict(self.config),
        }


@dataclass(frozen=True)
class ProviderInstanceConfig:
    provider_id: str
    plugin_id: str
    enabled: bool
    config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "config": dict(self.config),
        }


@dataclass(frozen=True)
class ToolInstanceConfig:
    tool_id: str
    plugin_id: str
    enabled: bool
    config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "tool_id": self.tool_id,
            "plugin_id": self.plugin_id,
            "enabled": self.enabled,
            "config": dict(self.config),
        }


@dataclass(frozen=True)
class WorkspaceConfig:
    root: Path
    mode: str

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "mode": self.mode,
        }


@dataclass(frozen=True)
class AgentMemoryConfig:
    hard_message_limit: int = 100
    dynamic_focus_enabled: bool = True
    dynamic_focus_messages: int = 10
    summary_trigger_messages: int = 20
    retrieval_max_results: int = 8

    def to_dict(self) -> dict[str, object]:
        return {
            "hard_message_limit": self.hard_message_limit,
            "dynamic_focus_enabled": self.dynamic_focus_enabled,
            "dynamic_focus_messages": self.dynamic_focus_messages,
            "summary_trigger_messages": self.summary_trigger_messages,
            "retrieval_max_results": self.retrieval_max_results,
        }


@dataclass(frozen=True)
class AgentLoggingConfig:
    level: str = "info"
    json_logs: bool = False
    log_events: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "json_logs": self.json_logs,
            "log_events": self.log_events,
        }


@dataclass(frozen=True)
class AgentConfig:
    default_provider: str | None
    require_provider: bool
    system_prompt_file: Path | None
    max_turns: int = 4
    memory: AgentMemoryConfig = field(default_factory=AgentMemoryConfig)
    logging: AgentLoggingConfig = field(default_factory=AgentLoggingConfig)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "default_provider": self.default_provider,
            "require_provider": self.require_provider,
            "max_turns": self.max_turns,
            "memory": self.memory.to_dict(),
            "logging": self.logging.to_dict(),
        }
        if self.system_prompt_file is not None:
            payload["system_prompt_file"] = str(self.system_prompt_file)
        return payload


@dataclass(frozen=True)
class RuntimeConfiguration:
    settings: Settings
    safe_mode: bool
    default_provider: str | None
    require_provider: bool
    agent: AgentConfig
    workspace: WorkspaceConfig
    transports: list[TransportInstanceConfig]
    providers: list[ProviderInstanceConfig]
    tools: list[ToolInstanceConfig]
    secrets: dict[str, str] = field(default_factory=dict)
    tool_secrets: dict[str, str] = field(default_factory=dict)
    raw_config: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "settings": self.settings.to_dict(),
            "safe_mode": self.safe_mode,
            "default_provider": self.default_provider,
            "require_provider": self.require_provider,
            "agent": self.agent.to_dict(),
            "workspace": self.workspace.to_dict(),
            "secret_keys": sorted(self.secrets),
            "tool_secret_keys": sorted(self.tool_secrets),
            "transports": [transport.to_dict() for transport in self.transports],
            "providers": [provider.to_dict() for provider in self.providers],
            "tools": [tool.to_dict() for tool in self.tools],
        }


def load_runtime_configuration(
    settings: Settings,
    environ: dict[str, str] | None = None,
) -> RuntimeConfiguration:
    env = dict(os.environ if environ is None else environ)
    raw_config = merge_runtime_config(read_raw_config(settings.config_file), env)
    transports = _parse_transports(raw_config)
    if not transports:
        transports = [
            TransportInstanceConfig(
                transport_id="console",
                plugin_id="builtin.console",
                enabled=True,
                config={},
            )
        ]
    providers = _parse_providers(raw_config)
    tools = _parse_tools(raw_config)
    workspace = _parse_workspace(raw_config, env)
    default_provider = _resolve_default_provider(raw_config, providers)
    require_provider = _parse_require_provider(raw_config)
    agent_config = _parse_agent_config(
        raw_config,
        settings=settings,
        default_provider=default_provider,
        require_provider=require_provider,
    )

    return RuntimeConfiguration(
        settings=settings,
        safe_mode=settings.safe_mode,
        default_provider=default_provider,
        require_provider=require_provider,
        agent=agent_config,
        workspace=workspace,
        transports=transports,
        providers=providers,
        tools=tools,
        secrets=load_secrets(settings.secrets_file),
        tool_secrets=load_secrets(settings.tool_secrets_file),
        raw_config=raw_config,
    )


def read_raw_config(config_file: Path) -> dict[str, object]:
    if not config_file.exists():
        return {}

    payload = tomllib.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items()}


def write_raw_config(config_file: Path, payload: dict[str, object]) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(render_toml(payload), encoding="utf-8")


def load_secrets(secrets_file: Path) -> dict[str, str]:
    if not secrets_file.exists():
        return {}

    secrets: dict[str, str] = {}
    for raw_line in secrets_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {'"', "'"}
        ):
            normalized_value = normalized_value[1:-1]
        secrets[key.strip()] = normalized_value
    return secrets


def render_default_config(settings: Settings) -> str:
    default_prompt_file = default_system_prompt_file(settings)
    return "\n".join(
        [
            "[updates]",
            f'channel = "{settings.channel}"',
            f'base_url = "{settings.update_base_url}"',
            "",
            "[runtime]",
            f"heartbeat_interval_seconds = {settings.heartbeat_interval_seconds}",
            f"safe_mode = {str(settings.safe_mode).lower()}",
            "",
            "[docker]",
            f'project_name = "{settings.docker_project_name}"',
            "",
            "[paths]",
            f'secrets_file = "{settings.secrets_file}"',
            f'tool_secrets_file = "{settings.tool_secrets_file}"',
            f'prompts_dir = "{settings.prompts_dir}"',
            f'plugins_dir = "{settings.plugins_dir}"',
            f'tools_dir = "{settings.tools_dir}"',
            f'providers_dir = "{settings.providers_dir}"',
            f'credentials_dir = "{settings.credentials_dir}"',
            "",
            "[workspace]",
            'root = ""',
            'mode = "bounded"',
            "",
            "[agent]",
            'default_provider = ""',
            "require_provider = false",
            f'system_prompt_file = "{default_prompt_file}"',
            "max_turns = 4",
            "",
            "[agent.memory]",
            "hard_message_limit = 100",
            "dynamic_focus_enabled = true",
            "dynamic_focus_messages = 10",
            "summary_trigger_messages = 20",
            "retrieval_max_results = 8",
            "",
            "[agent.logging]",
            'level = "info"',
            "json_logs = false",
            "log_events = true",
            "",
            "[transports.console]",
            'plugin = "builtin.console"',
            "enabled = true",
            "",
            "[transports.webhook]",
            'plugin = "builtin.webhook"',
            "enabled = false",
            'listen_host = "0.0.0.0"',
            "listen_port = 8080",
            'path = "/events"',
            'shared_secret_name = "NAGIENT_WEBHOOK_SHARED_SECRET"',
            "",
            "[transports.telegram]",
            'plugin = "builtin.telegram"',
            "enabled = false",
            'bot_token_secret = "TELEGRAM_BOT_TOKEN"',
            'default_chat_id = ""',
            "",
            "[providers.openai]",
            'plugin = "builtin.openai"',
            "enabled = false",
            'auth = "api_key"',
            'api_key_secret = "OPENAI_API_KEY"',
            'model = "gpt-4.1-mini"',
            "",
            "[providers.openai-codex]",
            'plugin = "builtin.openai_codex"',
            "enabled = false",
            'auth = "device_code"',
            'redirect_uri = "http://127.0.0.1:1455/auth/callback"',
            'api_key_secret = "CODEX_API_KEY"',
            'model = "gpt-5-codex"',
            "",
            "[providers.anthropic]",
            'plugin = "builtin.anthropic"',
            "enabled = false",
            'auth = "api_key"',
            'api_key_secret = "ANTHROPIC_API_KEY"',
            'model = "claude-sonnet-4-5"',
            "",
            "[providers.gemini]",
            'plugin = "builtin.gemini"',
            "enabled = false",
            'auth = "api_key"',
            'api_key_secret = "GEMINI_API_KEY"',
            'model = "gemini-2.5-pro"',
            "",
            "[providers.deepseek]",
            'plugin = "builtin.deepseek"',
            "enabled = false",
            'auth = "api_key"',
            'api_key_secret = "DEEPSEEK_API_KEY"',
            'model = "deepseek-chat"',
            "",
            "[providers.ollama]",
            'plugin = "builtin.ollama"',
            "enabled = false",
            'auth = "none"',
            'base_url = "http://127.0.0.1:11434"',
            'model = "llama3.1:8b"',
            "",
            "[tools.workspace_fs]",
            'plugin = "workspace.fs"',
            "enabled = true",
            "",
            "[tools.workspace_shell]",
            'plugin = "workspace.shell"',
            "enabled = true",
            "timeout_seconds = 15",
            "max_output_chars = 8000",
            "default_ping_count = 4",
            "normalize_infinite_commands = true",
            "enforce_finite_commands = true",
            "",
            "[tools.workspace_git]",
            'plugin = "workspace.git"',
            "enabled = true",
            '# author_name = "Nagient Agent"',
            '# author_email = "agent@example.com"',
            '# username = "git-user"',
            '# token_secret = "GIT_ACCESS_TOKEN"',
            "",
            "[tools.transport_interaction]",
            'plugin = "transport.interaction"',
            "enabled = true",
            "",
            "[tools.transport_router]",
            'plugin = "transport.router"',
            "enabled = true",
            "",
            "[tools.agent_memory]",
            'plugin = "agent.memory"',
            "enabled = true",
            "",
            "[tools.system_backup]",
            'plugin = "system.backup"',
            "enabled = true",
            "",
            "[tools.system_reconcile]",
            'plugin = "system.reconcile"',
            "enabled = true",
            "",
            "[tools.system_jobs]",
            'plugin = "system.jobs"',
            "enabled = true",
            "",
            "[tools.github_api]",
            'plugin = "github.api"',
            "enabled = false",
            'token_secret = "GITHUB_TOKEN"',
            "",
        ]
    ) + "\n"


def render_default_secrets() -> str:
    return "\n".join(
        [
            "# Fill only the secrets you actually use.",
            "# OPENAI_API_KEY=",
            "# CODEX_API_KEY=",
            "# ANTHROPIC_API_KEY=",
            "# GEMINI_API_KEY=",
            "# DEEPSEEK_API_KEY=",
            "# TELEGRAM_BOT_TOKEN=",
            "# NAGIENT_WEBHOOK_SHARED_SECRET=",
            "",
        ]
    )


def render_default_tool_secrets() -> str:
    return "\n".join(
        [
            "# Secrets for tool and connector integrations.",
            "# GIT_ACCESS_TOKEN=",
            "# GIT_PASSWORD=",
            "# GITHUB_TOKEN=",
            "",
        ]
    )


def render_default_system_prompt() -> str:
    return "\n".join(
        [
            "You are Nagient, a modular autonomous agent runtime.",
            "",
            "Core operating rules:",
            "- Use enabled tools instead of guessing when a tool can verify something.",
            (
                "- Keep actions scoped to the configured workspace unless a tool "
                "explicitly supports broader access."
            ),
            "- Prefer safe, reversible actions when possible.",
            (
                "- Use memory tools for durable notes and retrieval instead of "
                "pretending to remember hidden history."
            ),
            "- When sending outbound messages, choose the correct configured transport and target.",
            (
                "- Treat approvals, secure inputs, and secrets as workflow actions "
                "handled by the system."
            ),
            "",
            "Communication rules:",
            "- Be concise, clear, and action-oriented.",
            "- Explain what you are doing when executing multi-step work.",
            "- If tool results are incomplete, say so directly.",
            "",
        ]
    ) + "\n"


def render_plugins_readme() -> str:
    return "\n".join(
        [
            "# Nagient custom transport plugins",
            "",
            "Each plugin lives in its own directory and must contain at least:",
            "- `plugin.toml`",
            "- `transport.py`",
            "- `instructions.md`",
            "- `schema.json`",
            "",
            "Generate a new template with:",
            "",
            "```bash",
            "nagient transport scaffold --plugin-id your.plugin.id",
            "```",
            "",
        ]
    )


def render_providers_readme() -> str:
    return "\n".join(
        [
            "# Nagient custom provider plugins",
            "",
            "Each provider lives in its own directory and must contain at least:",
            "- `provider.toml`",
            "- `provider.py`",
            "- `schema.json`",
            "",
            "Generate a new template with:",
            "",
            "```bash",
            "nagient provider scaffold --plugin-id your.provider.id",
            "```",
            "",
        ]
    )


def render_tools_readme() -> str:
    return "\n".join(
        [
            "# Nagient custom tool plugins",
            "",
            "Each tool plugin lives in its own directory and must contain at least:",
            "- `tool.toml`",
            "- `tool.py`",
            "- `schema.json`",
            "",
            "Generate a new template with:",
            "",
            "```bash",
            "nagient tool scaffold --plugin-id your.tool.id",
            "```",
            "",
        ]
    )


def render_credentials_readme() -> str:
    return "\n".join(
        [
            "# Nagient credentials store",
            "",
            "This directory stores OAuth/device-login tokens and other non-env credentials.",
            "Files are managed by Nagient and should not be committed to source control.",
            "",
        ]
    )


def activation_report_path(settings: Settings) -> Path:
    return settings.state_dir / "activation-report.json"


def effective_config_path(settings: Settings) -> Path:
    return settings.state_dir / "effective-config.json"


def last_known_good_path(settings: Settings) -> Path:
    return settings.state_dir / "last-known-good.json"


def auth_sessions_dir(settings: Settings) -> Path:
    return settings.state_dir / "auth-sessions"


def secret_metadata_path(settings: Settings) -> Path:
    return settings.state_dir / "secrets" / "metadata.json"


def workflow_state_dir(settings: Settings) -> Path:
    return settings.state_dir / "workflows"


def _parse_transports(payload: dict[str, object]) -> list[TransportInstanceConfig]:
    raw_transports = payload.get("transports")
    if not isinstance(raw_transports, dict):
        return []

    transports: list[TransportInstanceConfig] = []
    for transport_id, values in raw_transports.items():
        if not isinstance(transport_id, str) or not isinstance(values, dict):
            continue
        plugin_id = values.get("plugin", f"builtin.{transport_id}")
        if not isinstance(plugin_id, str):
            plugin_id = str(plugin_id)
        enabled = _coerce_bool(values.get("enabled", True))
        transport_config = {
            str(key): value
            for key, value in values.items()
            if key not in {"plugin", "enabled"}
        }
        transports.append(
            TransportInstanceConfig(
                transport_id=transport_id,
                plugin_id=plugin_id,
                enabled=enabled,
                config=transport_config,
            )
        )
    return transports


def _parse_providers(payload: dict[str, object]) -> list[ProviderInstanceConfig]:
    raw_providers = payload.get("providers")
    if not isinstance(raw_providers, dict):
        return []

    providers: list[ProviderInstanceConfig] = []
    for provider_id, values in raw_providers.items():
        if not isinstance(provider_id, str) or not isinstance(values, dict):
            continue
        plugin_id = values.get("plugin", f"builtin.{provider_id}")
        if not isinstance(plugin_id, str):
            plugin_id = str(plugin_id)
        enabled = _coerce_bool(values.get("enabled", False))
        provider_config = {
            str(key): value
            for key, value in values.items()
            if key not in {"plugin", "enabled"}
        }
        providers.append(
            ProviderInstanceConfig(
                provider_id=provider_id,
                plugin_id=plugin_id,
                enabled=enabled,
                config=provider_config,
            )
        )
    return providers


def _parse_tools(payload: dict[str, object]) -> list[ToolInstanceConfig]:
    raw_tools = payload.get("tools")
    if not isinstance(raw_tools, dict):
        return _default_tools()

    tools: list[ToolInstanceConfig] = []
    for tool_id, values in raw_tools.items():
        if not isinstance(tool_id, str) or not isinstance(values, dict):
            continue
        plugin_id = values.get("plugin", tool_id.replace("_", "."))
        if not isinstance(plugin_id, str):
            plugin_id = str(plugin_id)
        enabled = _coerce_bool(values.get("enabled", True))
        tool_config = {
            str(key): value
            for key, value in values.items()
            if key not in {"plugin", "enabled"}
        }
        tools.append(
            ToolInstanceConfig(
                tool_id=tool_id,
                plugin_id=plugin_id,
                enabled=enabled,
                config=tool_config,
            )
        )
    return tools or _default_tools()


def _parse_workspace(
    payload: dict[str, object],
    environ: dict[str, str],
) -> WorkspaceConfig:
    raw_workspace = payload.get("workspace")
    root_value = environ.get("NAGIENT_WORKSPACE_ROOT", "")
    mode_value = environ.get("NAGIENT_WORKSPACE_MODE", "")
    if isinstance(raw_workspace, dict):
        if not root_value and isinstance(raw_workspace.get("root"), str):
            root_value = str(raw_workspace["root"])
        if not mode_value and isinstance(raw_workspace.get("mode"), str):
            mode_value = str(raw_workspace["mode"])

    resolved_root = Path(root_value).expanduser() if root_value.strip() else Path.cwd()
    if not resolved_root.is_absolute():
        resolved_root = (Path.cwd() / resolved_root).resolve()
    mode = mode_value.strip().lower() or "bounded"
    if mode not in {"bounded", "unsafe"}:
        mode = "bounded"
    return WorkspaceConfig(root=resolved_root.resolve(), mode=mode)


def _parse_default_provider(payload: dict[str, object]) -> str | None:
    agent = payload.get("agent")
    if not isinstance(agent, dict):
        return None
    default_provider = agent.get("default_provider")
    if isinstance(default_provider, str) and default_provider.strip():
        return default_provider.strip()
    return None


def _resolve_default_provider(
    payload: dict[str, object],
    providers: list[ProviderInstanceConfig],
) -> str | None:
    configured_default = _parse_default_provider(payload)
    if configured_default is not None:
        return configured_default
    if _has_explicit_default_provider_setting(payload):
        return None

    enabled_providers = [provider.provider_id for provider in providers if provider.enabled]
    if len(enabled_providers) == 1:
        return enabled_providers[0]
    return None


def _has_explicit_default_provider_setting(payload: dict[str, object]) -> bool:
    agent = payload.get("agent")
    return isinstance(agent, dict) and "default_provider" in agent


def _parse_require_provider(payload: dict[str, object]) -> bool:
    agent = payload.get("agent")
    if not isinstance(agent, dict):
        return False
    return _coerce_bool(agent.get("require_provider", False))


def _parse_agent_config(
    payload: dict[str, object],
    *,
    settings: Settings,
    default_provider: str | None,
    require_provider: bool,
) -> AgentConfig:
    agent = payload.get("agent")
    if not isinstance(agent, dict):
        agent = {}
    memory = agent.get("memory")
    if not isinstance(memory, dict):
        memory = {}
    logging = agent.get("logging")
    if not isinstance(logging, dict):
        logging = {}

    system_prompt_file = _resolve_optional_path(
        agent.get("system_prompt_file"),
        base_dir=settings.config_file.parent,
        fallback=default_system_prompt_file(settings),
    )
    max_turns = _positive_int(agent.get("max_turns"), default=4)
    return AgentConfig(
        default_provider=default_provider,
        require_provider=require_provider,
        system_prompt_file=system_prompt_file,
        max_turns=max_turns,
        memory=AgentMemoryConfig(
            hard_message_limit=_positive_int(
                memory.get("hard_message_limit"),
                default=100,
            ),
            dynamic_focus_enabled=_coerce_bool(
                memory.get("dynamic_focus_enabled", True)
            ),
            dynamic_focus_messages=_positive_int(
                memory.get("dynamic_focus_messages"),
                default=10,
            ),
            summary_trigger_messages=_positive_int(
                memory.get("summary_trigger_messages"),
                default=20,
            ),
            retrieval_max_results=_positive_int(
                memory.get("retrieval_max_results"),
                default=8,
            ),
        ),
        logging=AgentLoggingConfig(
            level=_normalize_log_level(logging.get("level", "info")),
            json_logs=_coerce_bool(logging.get("json_logs", False)),
            log_events=_coerce_bool(logging.get("log_events", True)),
        ),
    )


def _default_tools() -> list[ToolInstanceConfig]:
    return [
        ToolInstanceConfig("workspace_fs", "workspace.fs", True, {}),
        ToolInstanceConfig("workspace_shell", "workspace.shell", True, {}),
        ToolInstanceConfig("workspace_git", "workspace.git", True, {}),
        ToolInstanceConfig("transport_interaction", "transport.interaction", True, {}),
        ToolInstanceConfig("system_backup", "system.backup", True, {}),
        ToolInstanceConfig("system_reconcile", "system.reconcile", True, {}),
        ToolInstanceConfig("transport_router", "transport.router", True, {}),
        ToolInstanceConfig("agent_memory", "agent.memory", True, {}),
        ToolInstanceConfig("system_jobs", "system.jobs", True, {}),
    ]


def merge_runtime_config(
    payload: dict[str, object],
    environ: dict[str, str],
) -> dict[str, object]:
    merged: dict[str, object] = dict(payload)
    transports = merged.get("transports")
    if not isinstance(transports, dict):
        transports = {}
    transports = {
        str(transport_id): dict(values) if isinstance(values, dict) else {}
        for transport_id, values in transports.items()
    }
    providers = merged.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    providers = {
        str(provider_id): dict(values) if isinstance(values, dict) else {}
        for provider_id, values in providers.items()
    }
    tools = merged.get("tools")
    if not isinstance(tools, dict):
        tools = {}
    tools = {
        str(tool_id): dict(values) if isinstance(values, dict) else {}
        for tool_id, values in tools.items()
    }

    for key, value in environ.items():
        if key == "NAGIENT_AGENT_DEFAULT_PROVIDER":
            agent = _ensure_mapping(merged, "agent")
            agent["default_provider"] = value
            continue
        if key == "NAGIENT_AGENT_REQUIRE_PROVIDER":
            agent = _ensure_mapping(merged, "agent")
            agent["require_provider"] = _coerce_env_value(value)
            continue
        if key.startswith("NAGIENT_AGENT__"):
            parts = key.split("__")
            if len(parts) < 2:
                continue
            field_name = "__".join(parts[1:]).strip().lower()
            if not field_name:
                continue
            agent = _ensure_mapping(merged, "agent")
            agent[field_name] = _coerce_env_value(value)
            continue
        if key.startswith("NAGIENT_AGENT_MEMORY__"):
            parts = key.split("__")
            if len(parts) < 2:
                continue
            field_name = "__".join(parts[1:]).strip().lower()
            if not field_name:
                continue
            agent = _ensure_mapping(merged, "agent")
            memory = _ensure_nested_mapping(agent, "memory")
            memory[field_name] = _coerce_env_value(value)
            continue
        if key.startswith("NAGIENT_AGENT_LOGGING__"):
            parts = key.split("__")
            if len(parts) < 2:
                continue
            field_name = "__".join(parts[1:]).strip().lower()
            if not field_name:
                continue
            agent = _ensure_mapping(merged, "agent")
            logging = _ensure_nested_mapping(agent, "logging")
            logging[field_name] = _coerce_env_value(value)
            continue
        if key.startswith("NAGIENT_TRANSPORT__"):
            parts = key.split("__")
            if len(parts) < 3:
                continue
            transport_id = parts[1].strip().lower()
            field_name = "__".join(parts[2:]).strip().lower()
            if not transport_id or not field_name:
                continue
            transport_values = transports.get(transport_id, {})
            transport_values[field_name] = _coerce_env_value(value)
            transports[transport_id] = transport_values
            continue
        if key.startswith("NAGIENT_TOOL__"):
            parts = key.split("__")
            if len(parts) < 3:
                continue
            tool_id = parts[1].strip().lower()
            field_name = "__".join(parts[2:]).strip().lower()
            if not tool_id or not field_name:
                continue
            tool_values = tools.get(tool_id, {})
            tool_values[field_name] = _coerce_env_value(value)
            tools[tool_id] = tool_values
            continue
        if not key.startswith("NAGIENT_PROVIDER__"):
            continue
        parts = key.split("__")
        if len(parts) < 3:
            continue
        provider_id = parts[1].strip().lower()
        if provider_id not in providers:
            hyphenated_provider_id = provider_id.replace("_", "-")
            if hyphenated_provider_id in providers:
                provider_id = hyphenated_provider_id
        field_name = "__".join(parts[2:]).strip().lower()
        if not provider_id or not field_name:
            continue
        provider_values = providers.get(provider_id, {})
        provider_values[field_name] = _coerce_env_value(value)
        providers[provider_id] = provider_values

    if transports:
        merged["transports"] = transports
    if providers:
        merged["providers"] = providers
    if tools:
        merged["tools"] = tools
    return merged


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _coerce_env_value(value: str) -> Any:
    normalized = value.strip()
    lowered = normalized.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    if normalized.isdigit():
        return int(normalized)
    return value


def _ensure_mapping(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    created: dict[str, object] = {}
    payload[key] = created
    return created


def _ensure_nested_mapping(
    payload: dict[str, object],
    key: str,
) -> dict[str, object]:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    created: dict[str, object] = {}
    payload[key] = created
    return created


def _positive_int(value: object, *, default: int) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        if parsed > 0:
            return parsed
    return default


def _normalize_log_level(value: object) -> str:
    if not isinstance(value, str):
        return "info"
    normalized = value.strip().lower()
    if normalized in {"debug", "info", "warning", "error"}:
        return normalized
    return "info"


def _resolve_optional_path(
    raw_value: object,
    *,
    base_dir: Path,
    fallback: Path,
) -> Path:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return fallback.resolve()
    candidate = Path(raw_value).expanduser()
    if not candidate.is_absolute():
        candidate = (base_dir / candidate).resolve()
    return candidate.resolve()


def default_system_prompt_file(settings: Settings) -> Path:
    return (settings.prompts_dir / "system.md").resolve()


def render_toml(payload: dict[str, object]) -> str:
    lines: list[str] = []
    _render_toml_table(lines, payload, [])
    return "\n".join(lines).rstrip() + "\n"


def _render_toml_table(
    lines: list[str],
    payload: dict[str, object],
    prefix: list[str],
) -> None:
    scalar_items = [
        (key, value) for key, value in payload.items() if not isinstance(value, dict)
    ]
    nested_items = [
        (key, value) for key, value in payload.items() if isinstance(value, dict)
    ]
    if prefix:
        lines.append(f"[{'.'.join(prefix)}]")
    for key, value in scalar_items:
        lines.append(f"{key} = {_render_toml_value(value)}")
    if scalar_items and nested_items:
        lines.append("")
    for index, (key, value) in enumerate(nested_items):
        _render_toml_table(lines, value, [*prefix, key])
        if index != len(nested_items) - 1:
            lines.append("")


def _render_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_render_toml_value(item) for item in value) + "]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
