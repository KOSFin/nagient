from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import nagient.providers.scaffold as provider_scaffold
from nagient.app.configuration import (
    render_credentials_readme,
    render_default_config,
    render_default_secrets,
    render_default_tool_secrets,
    render_plugins_readme,
    render_providers_readme,
    render_tools_readme,
)
from nagient.app.settings import Settings
from nagient.plugins.scaffold import ScaffoldResult, scaffold_transport_plugin
from nagient.tools.scaffold import ScaffoldResult as ToolScaffoldResult
from nagient.tools.scaffold import scaffold_tool_plugin


@dataclass(frozen=True)
class ConfigurationService:
    settings: Settings

    def initialize(self, force: bool = False) -> dict[str, object]:
        self.settings.ensure_directories()
        written_files: list[str] = []

        file_payloads = {
            self.settings.config_file: render_default_config(self.settings),
            self.settings.secrets_file: render_default_secrets(),
            self.settings.tool_secrets_file: render_default_tool_secrets(),
            self.settings.plugins_dir / "README.md": render_plugins_readme(),
            self.settings.tools_dir / "README.md": render_tools_readme(),
            self.settings.providers_dir / "README.md": render_providers_readme(),
            self.settings.credentials_dir / "README.md": render_credentials_readme(),
        }
        for path, content in file_payloads.items():
            if path.exists() and not force:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            written_files.append(str(path))

        return {
            "home_dir": str(self.settings.home_dir),
            "config_file": str(self.settings.config_file),
            "secrets_file": str(self.settings.secrets_file),
            "tool_secrets_file": str(self.settings.tool_secrets_file),
            "plugins_dir": str(self.settings.plugins_dir),
            "tools_dir": str(self.settings.tools_dir),
            "providers_dir": str(self.settings.providers_dir),
            "credentials_dir": str(self.settings.credentials_dir),
            "force": force,
            "written_files": written_files,
        }

    def scaffold_transport(
        self,
        plugin_id: str,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> ScaffoldResult:
        target_dir = output_dir or self.settings.plugins_dir / plugin_id
        return scaffold_transport_plugin(
            plugin_id=plugin_id,
            output_dir=target_dir,
            force=force,
        )

    def scaffold_tool(
        self,
        plugin_id: str,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> ToolScaffoldResult:
        target_dir = output_dir or self.settings.tools_dir / plugin_id
        return scaffold_tool_plugin(
            plugin_id=plugin_id,
            output_dir=target_dir,
            force=force,
        )

    def scaffold_provider(
        self,
        plugin_id: str,
        output_dir: Path | None = None,
        force: bool = False,
    ) -> provider_scaffold.ScaffoldResult:
        target_dir = output_dir or self.settings.providers_dir / plugin_id
        return provider_scaffold.scaffold_provider_plugin(
            plugin_id=plugin_id,
            output_dir=target_dir,
            force=force,
        )
