from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from nagient.domain.entities.system_state import AuthSessionState, CredentialRecord


@dataclass(frozen=True)
class FileCredentialStore:
    credentials_dir: Path

    def load(self, provider_id: str) -> CredentialRecord | None:
        path = self._credential_path(provider_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return CredentialRecord.from_dict(payload)

    def save(self, provider_id: str, record: CredentialRecord) -> Path:
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        _set_private_permissions(self.credentials_dir, is_directory=True)
        path = self._credential_path(provider_id)
        path.write_text(json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8")
        _set_private_permissions(path, is_directory=False)
        return path

    def delete(self, provider_id: str) -> bool:
        path = self._credential_path(provider_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _credential_path(self, provider_id: str) -> Path:
        return self.credentials_dir / f"{_sanitize_identifier(provider_id)}.json"


@dataclass(frozen=True)
class AuthSessionStore:
    sessions_dir: Path

    def load(self, session_id: str) -> AuthSessionState | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return AuthSessionState.from_dict(payload)

    def save(self, session: AuthSessionState) -> Path:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        _set_private_permissions(self.sessions_dir, is_directory=True)
        path = self._session_path(session.session_id)
        path.write_text(json.dumps(session.to_dict(), indent=2) + "\n", encoding="utf-8")
        _set_private_permissions(path, is_directory=False)
        return path

    def delete(self, session_id: str) -> bool:
        path = self._session_path(session_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{_sanitize_identifier(session_id)}.json"


def _sanitize_identifier(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    return cleaned.strip("-") or "default"


def _set_private_permissions(path: Path, *, is_directory: bool) -> None:
    mode = 0o700 if is_directory else 0o600
    try:
        os.chmod(path, mode)
    except OSError:
        return

