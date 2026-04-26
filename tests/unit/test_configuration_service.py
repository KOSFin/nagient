from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nagient.app.container import build_container
from nagient.app.settings import Settings


class ConfigurationServiceTests(unittest.TestCase):
    def test_secret_reference_updates_reject_raw_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir) / ".nagient"
            settings = Settings.from_env({"NAGIENT_HOME": str(home_dir)})
            container = build_container(settings)
            container.configuration_service.initialize(force=True)

            with self.assertRaisesRegex(ValueError, "secret name like MY_SECRET"):
                container.configuration_service.configure_transport(
                    "telegram",
                    config_updates={"bot_token_secret": "123456:telegram-token"},
                )


if __name__ == "__main__":
    unittest.main()
