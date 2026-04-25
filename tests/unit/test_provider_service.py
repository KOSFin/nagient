from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.settings import Settings
from nagient.application.services.provider_service import ProviderService
from nagient.providers.manager import ProviderManager
from nagient.providers.registry import ProviderPluginRegistry
from nagient.providers.storage import AuthSessionStore, FileCredentialStore


class ProviderServiceTests(unittest.TestCase):
    def test_api_key_login_updates_secrets_and_auth_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[providers.openai]",
                        'plugin = "builtin.openai"',
                        "enabled = true",
                        'auth = "api_key"',
                        'api_key_secret = "OPENAI_API_KEY"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(home_dir),
                    "NAGIENT_CONFIG": str(config_file),
                }
            )
            service = ProviderService(
                settings=settings,
                provider_registry=ProviderPluginRegistry(),
                provider_manager=ProviderManager(),
                credential_store=FileCredentialStore(settings.credentials_dir),
                auth_session_store=AuthSessionStore(settings.state_dir / "auth-sessions"),
            )

            payload = service.login("openai", api_key="sk-test")

            self.assertEqual(payload["secret_name"], "OPENAI_API_KEY")
            self.assertTrue(payload["provider"]["authenticated"])
            secrets_text = settings.secrets_file.read_text(encoding="utf-8")
            self.assertIn("OPENAI_API_KEY=sk-test", secrets_text)

            logout_payload = service.logout("openai")
            self.assertFalse(logout_payload["provider"]["authenticated"])
            self.assertTrue(logout_payload["deleted_secret"])

    def test_stored_token_login_persists_credential_for_custom_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            providers_dir = home_dir / "providers"
            providers_dir.mkdir(parents=True, exist_ok=True)
            from nagient.providers.scaffold import scaffold_provider_plugin

            scaffold_provider_plugin(
                plugin_id="custom.provider",
                output_dir=providers_dir / "custom.provider",
            )
            config_file = home_dir / "config.toml"
            config_file.write_text(
                "\n".join(
                    [
                        "[providers.demo]",
                        'plugin = "custom.provider"',
                        "enabled = true",
                        'auth = "stored_token"',
                        'base_url = "https://example.invalid"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            settings = Settings.from_env(
                {
                    "NAGIENT_HOME": str(home_dir),
                    "NAGIENT_CONFIG": str(config_file),
                    "NAGIENT_PROVIDERS_DIR": str(providers_dir),
                }
            )
            service = ProviderService(
                settings=settings,
                provider_registry=ProviderPluginRegistry(),
                provider_manager=ProviderManager(),
                credential_store=FileCredentialStore(settings.credentials_dir),
                auth_session_store=AuthSessionStore(settings.state_dir / "auth-sessions"),
            )

            payload = service.login("demo", token="demo-token")
            models_payload = service.list_models("demo")

            self.assertTrue(payload["provider"]["authenticated"])
            self.assertEqual(models_payload["models"][0]["model_id"], "custom-model")


if __name__ == "__main__":
    unittest.main()
