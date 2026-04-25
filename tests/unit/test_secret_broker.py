from __future__ import annotations

import tempfile
import unittest

from nagient.app.settings import Settings
from nagient.security.broker import SecretBroker


class SecretBrokerTests(unittest.TestCase):
    def test_store_bind_resolve_and_redact_tool_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            broker = SecretBroker(settings)

            broker.store_secret("GITHUB_TOKEN", "ghs-secret", scope="tool")
            broker.bind_secret(
                "GITHUB_TOKEN",
                target_kind="tool",
                target_id="github_api",
                scope_hint="tool",
            )

            self.assertEqual(
                broker.resolve_secret("GITHUB_TOKEN", scope_hint="tool"),
                "ghs-secret",
            )
            metadata = broker.list_metadata("tool")
            self.assertEqual(metadata[0].bindings[0].target_id, "github_api")
            self.assertEqual(
                broker.redact_text("Authorization: ghs-secret"),
                "Authorization: <redacted:GITHUB_TOKEN>",
            )

    def test_validate_secret_reference_returns_issue_for_missing_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / "home"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            broker = SecretBroker(settings)

            issues = broker.validate_secret_reference(
                "MISSING_SECRET",
                scope_hint="tool",
                source="tool.github",
            )

            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].code, "secret.missing")


if __name__ == "__main__":
    unittest.main()
