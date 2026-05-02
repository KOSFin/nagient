from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nagient.app.configuration import (
    RuntimeConfiguration,
    TransportInstanceConfig,
    load_runtime_configuration,
)
from nagient.app.settings import Settings
from nagient.infrastructure.logging import RuntimeLogger
from nagient.plugins.base import LoadedTransportPlugin
from nagient.plugins.registry import TransportPluginRegistry


@dataclass
class TransportRouterService:
    settings: Settings
    plugin_registry: TransportPluginRegistry
    logger: RuntimeLogger

    def list_transports(self) -> list[dict[str, object]]:
        runtime_config = load_runtime_configuration(self.settings)
        discovery = self.plugin_registry.discover(self.settings.plugins_dir)
        items: list[dict[str, object]] = []
        for transport in runtime_config.transports:
            plugin = discovery.plugins.get(transport.plugin_id)
            items.append(
                {
                    "transport_id": transport.transport_id,
                    "plugin_id": transport.plugin_id,
                    "enabled": transport.enabled,
                    "namespace": plugin.manifest.namespace if plugin else "",
                    "required_slots": (
                        dict(plugin.manifest.required_slots) if plugin else {}
                    ),
                    "functions": plugin.manifest.exposed_functions if plugin else [],
                    "custom_functions": (
                        list(plugin.manifest.custom_functions) if plugin else []
                    ),
                    "default_target_available": (
                        self._default_target_available(transport)
                        if plugin
                        else False
                    ),
                    "default_target_field": (
                        self._default_target_field(transport)
                        if plugin
                        else ""
                    ),
                    "send_message_hint": (
                        self._send_message_hint(transport)
                        if plugin
                        else ""
                    ),
                }
            )
        self.logger.debug(
            "transport.list",
            "Listed configured transports.",
            transports=len(items),
        )
        return items

    def send_message(
        self,
        *,
        transport_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return self._invoke_standard(
            transport_id=transport_id,
            slot_name="send_message",
            payload=payload,
        )

    def send_notification(
        self,
        *,
        transport_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return self._invoke_standard(
            transport_id=transport_id,
            slot_name="send_notification",
            payload=payload,
        )

    def invoke_custom(
        self,
        *,
        transport_id: str,
        function_name: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        runtime_config, transport, plugin = self._resolve_transport(transport_id)
        prepared_payload = self._attach_runtime_payload(
            runtime_config,
            transport,
            dict(payload),
        )
        function = self._resolve_bound_function(plugin, function_name)
        result = function(prepared_payload)
        self.logger.info(
            "transport.invoke_custom",
            "Invoked transport custom function.",
            transport_id=transport_id,
            plugin_id=plugin.manifest.plugin_id,
            function_name=function_name,
        )
        if not isinstance(result, dict):
            raise ValueError("Transport custom function must return a dictionary payload.")
        return result

    def send_typing(
        self,
        *,
        transport_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        runtime_config, transport, plugin = self._resolve_transport(transport_id)
        prepared_payload = self._attach_runtime_payload(
            runtime_config,
            transport,
            dict(payload),
        )
        for function_name in (
            f"{plugin.manifest.namespace}.sendTyping",
            f"{plugin.manifest.namespace}.sendChatAction",
        ):
            if function_name not in plugin.manifest.function_bindings:
                continue
            if function_name.endswith("sendChatAction"):
                prepared_payload.setdefault("action", "typing")
            function = self._resolve_bound_function(plugin, function_name)
            result = function(prepared_payload)
            if not isinstance(result, dict):
                raise ValueError("Transport typing function must return a dictionary payload.")
            self.logger.info(
                "transport.send_typing",
                "Sent transport typing indicator.",
                transport_id=transport_id,
                plugin_id=plugin.manifest.plugin_id,
                function_name=function_name,
            )
            return result
        raise ValueError(
            f"Transport {transport_id!r} does not expose a typing capability."
        )

    def _invoke_standard(
        self,
        *,
        transport_id: str,
        slot_name: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        runtime_config, transport, plugin = self._resolve_transport(transport_id)
        exposed_name = plugin.manifest.required_slots.get(slot_name)
        if exposed_name is None:
            raise ValueError(
                f"Transport plugin {plugin.manifest.plugin_id!r} does not define slot "
                f"{slot_name!r}."
            )
        prepared_payload = self._attach_runtime_payload(
            runtime_config,
            transport,
            dict(payload),
        )
        function = self._resolve_bound_function(plugin, exposed_name)
        result = function(prepared_payload)
        self.logger.info(
            f"transport.{slot_name}",
            "Invoked standard transport function.",
            transport_id=transport_id,
            plugin_id=plugin.manifest.plugin_id,
            function_name=exposed_name,
        )
        if not isinstance(result, dict):
            raise ValueError("Transport function must return a dictionary payload.")
        return result

    def _resolve_transport(
        self,
        transport_id: str,
    ) -> tuple[RuntimeConfiguration, TransportInstanceConfig, LoadedTransportPlugin]:
        runtime_config = load_runtime_configuration(self.settings)
        transport = next(
            (item for item in runtime_config.transports if item.transport_id == transport_id),
            None,
        )
        if transport is None:
            raise ValueError(f"Transport {transport_id!r} is not configured.")
        if not transport.enabled:
            raise ValueError(f"Transport {transport_id!r} is disabled.")
        discovery = self.plugin_registry.discover(self.settings.plugins_dir)
        plugin = discovery.plugins.get(transport.plugin_id)
        if plugin is None:
            raise ValueError(
                f"Transport {transport_id!r} references unknown plugin "
                f"{transport.plugin_id!r}."
            )
        return runtime_config, transport, plugin

    def _resolve_bound_function(
        self,
        plugin: LoadedTransportPlugin,
        function_name: str,
    ) -> Any:
        binding_name = plugin.manifest.function_bindings.get(function_name)
        if binding_name is None:
            raise ValueError(
                f"Transport plugin {plugin.manifest.plugin_id!r} does not expose "
                f"{function_name!r}."
            )
        function = getattr(plugin.implementation, binding_name, None)
        if not callable(function):
            raise ValueError(
                f"Transport plugin {plugin.manifest.plugin_id!r} has non-callable binding "
                f"{binding_name!r}."
            )
        return function

    def _attach_runtime_payload(
        self,
        runtime_config: RuntimeConfiguration,
        transport: TransportInstanceConfig,
        payload: dict[str, object],
    ) -> dict[str, object]:
        payload.setdefault("_transport_config", dict(transport.config))
        payload.setdefault("_transport_id", transport.transport_id)
        if transport.plugin_id == "builtin.telegram":
            secret_name = transport.config.get("bot_token_secret")
            if isinstance(secret_name, str) and secret_name in runtime_config.secrets:
                payload.setdefault("_token", runtime_config.secrets[secret_name])
        return payload

    def _default_target_available(
        self,
        transport: TransportInstanceConfig,
    ) -> bool:
        if transport.plugin_id == "builtin.telegram":
            value = transport.config.get("default_chat_id", "")
            return bool(str(value).strip())
        if transport.plugin_id == "builtin.console":
            return True
        return False

    def _default_target_field(
        self,
        transport: TransportInstanceConfig,
    ) -> str:
        if transport.plugin_id == "builtin.telegram":
            return "chat_id"
        return ""

    def _send_message_hint(
        self,
        transport: TransportInstanceConfig,
    ) -> str:
        if transport.plugin_id == "builtin.telegram":
            if self._default_target_available(transport):
                return (
                    "Use transport.router.send_message with payload.text and transport_id "
                    "telegram. chat_id may be omitted because a default outbound chat is "
                    "configured."
                )
            return (
                "Use transport.router.send_message with payload.text and an explicit chat_id "
                "unless you are replying to a Telegram inbound event."
            )
        if transport.plugin_id == "builtin.console":
            return (
                "Use transport.router.send_message with payload.text to print a message into "
                "the local console chat."
            )
        return ""
