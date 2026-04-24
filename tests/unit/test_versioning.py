from __future__ import annotations

import unittest

from nagient.domain.versioning import Version


class VersioningTests(unittest.TestCase):
    def test_parse_and_stringify_roundtrip(self) -> None:
        version = Version.parse("1.2.3-rc.1")
        self.assertEqual(str(version), "1.2.3-rc.1")

    def test_release_is_greater_than_prerelease(self) -> None:
        prerelease = Version.parse("1.2.3-rc.1")
        release = Version.parse("1.2.3")
        self.assertLess(prerelease, release)

    def test_numeric_prerelease_segments_are_compared_numerically(self) -> None:
        lower = Version.parse("1.2.3-rc.2")
        higher = Version.parse("1.2.3-rc.10")
        self.assertLess(lower, higher)


if __name__ == "__main__":
    unittest.main()
