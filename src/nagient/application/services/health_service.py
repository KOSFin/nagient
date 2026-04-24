from __future__ import annotations

from dataclasses import dataclass

from nagient.app.settings import Settings


@dataclass(frozen=True)
class HealthService:
    settings: Settings

    def collect(self) -> dict[str, object]:
        return {
            "service": "nagient",
            "version": self.settings.version,
            "channel": self.settings.channel,
            "update_base_url": self.settings.update_base_url,
            "paths": {
                "home": str(self.settings.home_dir),
                "config": str(self.settings.config_file),
                "state": str(self.settings.state_dir),
                "logs": str(self.settings.log_dir),
                "releases": str(self.settings.releases_dir),
            },
        }

