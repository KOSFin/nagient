from __future__ import annotations

import unittest

from nagient.application.services.update_service import UpdateService
from nagient.infrastructure.registry import ManifestRegistry
from tests.bootstrap import FIXTURES_ROOT


class UpdateServiceTests(unittest.TestCase):
    def test_check_returns_latest_release_for_channel(self) -> None:
        registry = ManifestRegistry(str(FIXTURES_ROOT / "update_center"))
        service = UpdateService(registry=registry)

        notice = service.check(current_version="0.1.0", channel="stable")

        self.assertTrue(notice.update_available)
        self.assertEqual(str(notice.target_version), "0.2.0")
        self.assertEqual([step.step_id for step in notice.planned_migrations], ["state-sync-0.2.0"])

    def test_check_returns_up_to_date_when_versions_match(self) -> None:
        registry = ManifestRegistry(str(FIXTURES_ROOT / "update_center"))
        service = UpdateService(registry=registry)

        notice = service.check(current_version="0.2.0", channel="stable")

        self.assertFalse(notice.update_available)
        self.assertIn("Already up to date", notice.message)


if __name__ == "__main__":
    unittest.main()
