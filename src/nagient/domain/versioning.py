from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering

_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?$"
)


@total_ordering
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> Version:
        match = _SEMVER_PATTERN.match(value.strip())
        if not match:
            msg = f"Unsupported version string: {value!r}"
            raise ValueError(msg)

        prerelease = match.group("prerelease")
        prerelease_parts = tuple(prerelease.split(".")) if prerelease else ()
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=prerelease_parts,
        )

    def __str__(self) -> str:
        suffix = f"-{'.'.join(self.prerelease)}" if self.prerelease else ""
        return f"{self.major}.{self.minor}.{self.patch}{suffix}"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented

        current = (self.major, self.minor, self.patch)
        target = (other.major, other.minor, other.patch)
        if current != target:
            return current < target

        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and not other.prerelease:
            return True
        return self._compare_prerelease(self.prerelease, other.prerelease) < 0

    @staticmethod
    def _compare_prerelease(left: tuple[str, ...], right: tuple[str, ...]) -> int:
        if left == right:
            return 0
        if not left:
            return 1
        if not right:
            return -1

        for left_part, right_part in zip(left, right, strict=False):
            if left_part == right_part:
                continue
            left_numeric = left_part.isdigit()
            right_numeric = right_part.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left_part) < int(right_part) else 1
            if left_numeric and not right_numeric:
                return -1
            if not left_numeric and right_numeric:
                return 1
            return -1 if left_part < right_part else 1

        if len(left) == len(right):
            return 0
        return -1 if len(left) < len(right) else 1
