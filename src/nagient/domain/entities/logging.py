from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginLogChannelSpec:
    name: str
    description: str = ""
    default_level: str = "info"

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "default_level": self.default_level,
        }
