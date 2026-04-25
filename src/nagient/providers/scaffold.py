from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScaffoldResult:
    plugin_id: str
    output_dir: Path
    files: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "output_dir": str(self.output_dir),
            "files": self.files,
        }


def scaffold_provider_plugin(
    plugin_id: str,
    output_dir: Path,
    force: bool = False,
) -> ScaffoldResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "provider.toml": _render_manifest(plugin_id),
        "schema.json": _render_schema(),
        "provider.py": _render_provider_python(plugin_id),
        "README.md": _render_readme(plugin_id),
        "tests/test_provider.py": _render_test_file(),
    }

    written_files: list[str] = []
    for relative_path, content in files.items():
        file_path = output_dir / relative_path
        if file_path.exists() and not force:
            raise FileExistsError(
                f"Refusing to overwrite existing file {file_path} without force=True."
            )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        written_files.append(relative_path)

    return ScaffoldResult(
        plugin_id=plugin_id,
        output_dir=output_dir,
        files=written_files,
    )


def _render_manifest(plugin_id: str) -> str:
    return "\n".join(
        [
            f'id = "{plugin_id}"',
            'type = "provider"',
            'version = "0.1.0"',
            f'display_name = "{plugin_id}"',
            'family = "custom"',
            'entrypoint = "provider.py"',
            'config_schema_file = "schema.json"',
            "",
            'supported_auth_modes = ["api_key", "stored_token"]',
            'default_auth_mode = "api_key"',
            'capabilities = ["list_models", "api_key_auth"]',
            "",
            'required_config = ["base_url"]',
            (
                'optional_config = ["auth", "api_key_secret", "model", '
                '"models_path", "timeout_seconds"]'
            ),
            'secret_config = ["api_key_secret"]',
            'credential_fields = ["access_token", "refresh_token", "expires_at"]',
            "",
        ]
    )


def _render_schema() -> str:
    return "\n".join(
        [
            "{",
            '  "type": "object",',
            '  "required": ["base_url"],',
            '  "properties": {',
            '    "auth": {',
            '      "type": "string"',
            "    },",
            '    "base_url": {',
            '      "type": "string"',
            "    },",
            '    "api_key_secret": {',
            '      "type": "string"',
            "    },",
            '    "model": {',
            '      "type": "string"',
            "    },",
            '    "models_path": {',
            '      "type": "string"',
            "    },",
            '    "timeout_seconds": {',
            '      "type": "integer",',
            '      "minimum": 1',
            "    }",
            "  }",
            "}",
            "",
        ]
    )


def _render_provider_python(plugin_id: str) -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "import time",
            "import uuid",
            "from collections.abc import Mapping",
            "",
            "from nagient.domain.entities.system_state import (",
            "    AuthSessionState,",
            "    CheckIssue,",
            "    CredentialRecord,",
            "    ProviderAuthStatus,",
            "    ProviderModel,",
            ")",
            "from nagient.providers.base import BaseProviderPlugin",
            "",
            "",
            "class ProviderPlugin(BaseProviderPlugin):",
            "    def validate_config(",
            "        self,",
            "        provider_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "        credential: CredentialRecord | None,",
            "    ) -> list[CheckIssue]:",
            "        del secrets, credential",
            "        issues: list[CheckIssue] = []",
            '        base_url = config.get("base_url")',
            "        if not isinstance(base_url, str) or not base_url.startswith((\"http://\", \"https://\")):",
            "            issues.append(",
            "                CheckIssue(",
            '                    severity=\"error\",',
            '                    code=\"provider.invalid_base_url\",',
            "                    message=(",
            '                        f\"Provider {provider_id!r} must define base_url \"',
            '                        \"starting with http:// or https://.\"',
            "                    ),",
            "                    source=provider_id,",
            "                )",
            "            )",
            "        return issues",
            "",
            "    def auth_status(",
            "        self,",
            "        provider_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "        credential: CredentialRecord | None,",
            "    ) -> ProviderAuthStatus:",
            "        del provider_id, config",
            '        secret_name = "CUSTOM_PROVIDER_API_KEY"',
            "        if secret_name in secrets:",
            "            return ProviderAuthStatus(",
            "                authenticated=True,",
            '                auth_mode="api_key",',
            '                status="ready",',
            '                message=f"Secret {secret_name!r} is configured.",',
            "            )",
            "        if credential and credential.data.get(\"access_token\"):",
            "            return ProviderAuthStatus(",
            "                authenticated=True,",
            '                auth_mode="stored_token",',
            '                status="ready",',
            '                message="Stored token is available.",',
            "            )",
            "        return ProviderAuthStatus(",
            "            authenticated=False,",
            '            auth_mode="api_key",',
            '            status="missing_credentials",',
            '            message="No API key or stored token is configured.",',
            "            issues=[",
            "                CheckIssue(",
            '                    severity="warning",',
            '                    code="provider.credentials_missing",',
            "                    message=(",
            '                        f"Provider {provider_id!r} does not have credentials "',
            '                        "yet."',
            "                    ),",
            "                    source=provider_id,",
            "                )",
            "            ],",
            "        )",
            "",
            "    def self_test(",
            "        self,",
            "        provider_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "        credential: CredentialRecord | None,",
            "    ) -> list[CheckIssue]:",
            "        del provider_id, config, secrets, credential",
            "        return []",
            "",
            "    def healthcheck(",
            "        self,",
            "        provider_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "        credential: CredentialRecord | None,",
            "    ) -> list[CheckIssue]:",
            "        del provider_id, config, secrets, credential",
            "        return []",
            "",
            "    def begin_login(",
            "        self,",
            "        provider_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "        credential: CredentialRecord | None,",
            "    ) -> AuthSessionState:",
            "        del config, secrets, credential",
            "        return AuthSessionState(",
            "            session_id=str(uuid.uuid4()),",
            "            provider_id=provider_id,",
            f"            plugin_id=\"{plugin_id}\",",
            '            auth_mode="browser_callback",',
            '            status="pending",',
            '            submission_mode="callback_url",',
            "            instructions=[",
            '                "Open the authorization URL in a browser.",',
            (
                '                "After signing in, paste the callback URL into '
                '`nagient auth complete`.",'
            ),
            "            ],",
            '            authorization_url="https://example.invalid/oauth/start",',
            '            callback_url="https://example.invalid/oauth/callback",',
            "        )",
            "",
            "    def complete_login(",
            "        self,",
            "        provider_id: str,",
            "        config: Mapping[str, object],",
            "        credential: CredentialRecord | None,",
            "        session: AuthSessionState,",
            "        *,",
            "        callback_url: str | None = None,",
            "        code: str | None = None,",
            "    ) -> CredentialRecord:",
            "        del config, credential, session",
            "        token = code or callback_url or \"demo-token\"",
            "        return CredentialRecord(",
            "            provider_id=provider_id,",
            f"            plugin_id=\"{plugin_id}\",",
            '            auth_mode="stored_token",',
            '            issued_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),',
            '            data={"access_token": token},',
            "        )",
            "",
            "    def logout(",
            "        self,",
            "        provider_id: str,",
            "        config: Mapping[str, object],",
            "        credential: CredentialRecord | None,",
            "    ) -> None:",
            "        del provider_id, config, credential",
            "        return None",
            "",
            "    def list_models(",
            "        self,",
            "        provider_id: str,",
            "        config: Mapping[str, object],",
            "        secrets: Mapping[str, str],",
            "        credential: CredentialRecord | None,",
            "    ) -> list[ProviderModel]:",
            "        del provider_id, config, secrets, credential",
            "        return [",
            "            ProviderModel(",
            '                model_id="custom-model",',
            '                display_name="Custom Model",',
            '                metadata={"plugin": "custom"},',
            "            )",
            "        ]",
            "",
            "",
            "def build_plugin() -> ProviderPlugin:",
            "    return ProviderPlugin()",
            "",
        ]
    )


def _render_readme(plugin_id: str) -> str:
    return "\n".join(
        [
            f"# {plugin_id}",
            "",
            "This directory contains a custom Nagient provider plugin scaffold.",
            "",
            (
                "Edit `provider.toml` to describe provider capabilities and "
                "`provider.py` to implement auth + model discovery."
            ),
            (
                "Then configure the provider profile in `config.toml` and run "
                "`nagient preflight`, `nagient auth status`, or `nagient provider models`."
            ),
            "",
        ]
    )


def _render_test_file() -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "import importlib.util",
            "import sys",
            "import unittest",
            "from pathlib import Path",
            "",
            "",
            "class ProviderContractTests(unittest.TestCase):",
            "    def test_build_plugin_returns_object_with_required_methods(self) -> None:",
            "        provider_path = Path(__file__).resolve().parents[1] / 'provider.py'",
            (
                "        spec = importlib.util.spec_from_file_location("
                "'scaffold_provider', provider_path)"
            ),
            "        self.assertIsNotNone(spec)",
            "        self.assertIsNotNone(spec.loader)",
            "        module = importlib.util.module_from_spec(spec)",
            "        sys.modules['scaffold_provider'] = module",
            "        assert spec.loader is not None",
            "        spec.loader.exec_module(module)",
            "",
            "        plugin = module.build_plugin()",
            "        for attribute_name in [",
            "            'validate_config',",
            "            'self_test',",
            "            'healthcheck',",
            "            'auth_status',",
            "            'begin_login',",
            "            'complete_login',",
            "            'logout',",
            "            'list_models',",
            "        ]:",
            "            self.assertTrue(",
            "                callable(getattr(plugin, attribute_name, None)),",
            "                msg=attribute_name,",
            "            )",
            "",
            "",
            "if __name__ == '__main__':",
            "    unittest.main()",
            "",
        ]
    )
