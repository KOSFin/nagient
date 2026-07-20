from __future__ import annotations

import unittest

from nagient.plugins.catalog import catalog_entry, catalog_payload


class PluginCatalogTests(unittest.TestCase):
    def test_catalog_contains_verified_bundled_transports(self) -> None:
        payload = catalog_payload(family="transport", verified_only=True)
        self.assertEqual(payload["count"], 4)
        ids = {item["plugin_id"] for item in payload["plugins"]}  # type: ignore[index]
        self.assertIn("builtin.telegram", ids)

    def test_external_catalog_entry_is_pinned(self) -> None:
        entry = catalog_entry("nagient.telegram")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.ref, "v0.1.0")
        self.assertFalse(entry.bundled)

    def test_catalog_entry_is_case_insensitive(self) -> None:
        entry = catalog_entry("BUILTIN.TELEGRAM")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertTrue(entry.bundled)


if __name__ == "__main__":
    unittest.main()
