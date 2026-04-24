from __future__ import annotations

import json
import unittest

from nagient.infrastructure.manifests import (
    channel_to_dict,
    parse_channel_manifest,
    parse_release_manifest,
    release_to_dict,
)
from tests.bootstrap import FIXTURES_ROOT


class ManifestParsingTests(unittest.TestCase):
    def test_parse_channel_manifest(self) -> None:
        payload = json.loads(
            (FIXTURES_ROOT / "update_center" / "channels" / "stable.json").read_text(
                encoding="utf-8"
            )
        )
        manifest = parse_channel_manifest(payload)
        self.assertEqual(manifest.channel, "stable")
        self.assertEqual(str(manifest.latest_version), "0.2.0")
        self.assertEqual(channel_to_dict(manifest)["manifest_url"], "manifests/0.2.0.json")

    def test_parse_release_manifest_roundtrip(self) -> None:
        payload = json.loads(
            (FIXTURES_ROOT / "update_center" / "manifests" / "0.2.0.json").read_text(
                encoding="utf-8"
            )
        )
        manifest = parse_release_manifest(payload)
        serialized = release_to_dict(manifest)
        self.assertEqual(serialized["version"], "0.2.0")
        self.assertEqual(serialized["docker"]["image"], "nagient:0.2.0")
        self.assertEqual(len(serialized["artifacts"]), 7)
        self.assertEqual(len(serialized["migrations"]), 2)


if __name__ == "__main__":
    unittest.main()
