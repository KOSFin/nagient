from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from nagient.app.configuration import load_secrets, secret_metadata_path
from nagient.app.settings import Settings
from nagient.domain.entities.security import SecretBinding, SecretMetadata
from nagient.domain.entities.system_state import CheckIssue


@dataclass(frozen=True)
class SecretBroker:
    settings: Settings

    def list_metadata(self, scope: str | None = None) -> list[SecretMetadata]:
        metadata = self._load_metadata_with_env_fallbacks()
        if scope is None:
            return sorted(metadata.values(), key=lambda item: item.name)
        return sorted(
            [item for item in metadata.values() if item.scope == scope],
            key=lambda item: item.name,
        )

    def has_secret(self, name: str, *, scope_hint: str | None = None) -> bool:
        return self._resolve_optional(name, scope_hint=scope_hint) is not None

    def resolve_secret(self, name: str, *, scope_hint: str | None = None) -> str:
        resolved = self._resolve_optional(name, scope_hint=scope_hint)
        if resolved is None:
            raise KeyError(name)
        return resolved

    def resolve_many(
        self,
        names: list[str],
        *,
        scope_hint: str | None = None,
    ) -> dict[str, str]:
        return {
            name: self.resolve_secret(name, scope_hint=scope_hint)
            for name in names
        }

    def store_secret(
        self,
        name: str,
        value: str,
        *,
        scope: str,
        bindings: list[SecretBinding] | None = None,
    ) -> SecretMetadata:
        target_file = self._scope_file(scope)
        upsert_env_value(target_file, name, value)
        metadata = self._load_metadata()
        current = metadata.get(name)
        record = SecretMetadata(
            name=name,
            scope=scope,
            exists=True,
            bindings=bindings or (current.bindings if current else []),
            created_at=current.created_at if current else _utc_now(),
            updated_at=_utc_now(),
        )
        metadata[name] = record
        self._save_metadata(metadata)
        return record

    def bind_secret(
        self,
        name: str,
        *,
        target_kind: str,
        target_id: str,
        scope_hint: str | None = None,
    ) -> SecretMetadata:
        metadata = self._load_metadata()
        current = metadata.get(name)
        scope = scope_hint or (current.scope if current else "tool")
        bindings = list(current.bindings) if current else []
        binding = SecretBinding(target_kind=target_kind, target_id=target_id)
        if not any(
            item.target_kind == binding.target_kind and item.target_id == binding.target_id
            for item in bindings
        ):
            bindings.append(binding)
        record = SecretMetadata(
            name=name,
            scope=scope,
            exists=self.has_secret(name, scope_hint=scope),
            bindings=bindings,
            created_at=current.created_at if current else _utc_now(),
            updated_at=_utc_now(),
        )
        metadata[name] = record
        self._save_metadata(metadata)
        return record

    def remove_secret(self, name: str, *, scope_hint: str | None = None) -> bool:
        scopes = [scope_hint] if scope_hint else ["core", "tool"]
        removed = False
        for scope in scopes:
            if scope is None:
                continue
            removed = remove_env_value(self._scope_file(scope), name) or removed
        metadata = self._load_metadata()
        if name in metadata:
            current = metadata[name]
            metadata[name] = SecretMetadata(
                name=current.name,
                scope=current.scope,
                exists=False,
                bindings=current.bindings,
                created_at=current.created_at,
                updated_at=_utc_now(),
            )
            self._save_metadata(metadata)
        return removed

    def validate_secret_reference(
        self,
        name: str,
        *,
        scope_hint: str | None = None,
        source: str,
    ) -> list[CheckIssue]:
        if self.has_secret(name, scope_hint=scope_hint):
            return []
        return [
            CheckIssue(
                severity="error",
                code="secret.missing",
                message=f"Secret {name!r} is not configured.",
                source=source,
            )
        ]

    def self_check(self) -> list[CheckIssue]:
        issues: list[CheckIssue] = []
        metadata = self._load_metadata()
        secrets = {
            **load_secrets(self.settings.secrets_file),
            **load_secrets(self.settings.tool_secrets_file),
        }
        for name, record in metadata.items():
            if record.exists and name not in secrets:
                issues.append(
                    CheckIssue(
                        severity="warning",
                        code="secret.metadata_out_of_sync",
                        message=f"Secret metadata for {name!r} exists without a stored value.",
                        source="secret_broker",
                    )
                )
        return issues

    def redact_text(self, text: str) -> str:
        redacted = text
        secrets = sorted(
            {
                **load_secrets(self.settings.secrets_file),
                **load_secrets(self.settings.tool_secrets_file),
            }.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
        for name, value in secrets:
            if value:
                redacted = redacted.replace(value, f"<redacted:{name}>")
        return redacted

    def redact_value(self, value: object) -> object:
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, list):
            return [self.redact_value(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self.redact_value(item) for key, item in value.items()}
        return value

    def _resolve_optional(self, name: str, scope_hint: str | None = None) -> str | None:
        if scope_hint == "core":
            return load_secrets(self.settings.secrets_file).get(name)
        if scope_hint == "tool":
            return load_secrets(self.settings.tool_secrets_file).get(name)

        core = load_secrets(self.settings.secrets_file)
        if name in core:
            return core[name]
        tool = load_secrets(self.settings.tool_secrets_file)
        return tool.get(name)

    def _scope_file(self, scope: str) -> Path:
        if scope == "core":
            return self.settings.secrets_file
        if scope == "tool":
            return self.settings.tool_secrets_file
        raise ValueError(f"Unsupported secret scope {scope!r}.")

    def _load_metadata(self) -> dict[str, SecretMetadata]:
        path = secret_metadata_path(self.settings)
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        items = payload.get("secrets", [])
        if not isinstance(items, list):
            return {}
        metadata: dict[str, SecretMetadata] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            record = SecretMetadata.from_dict(item)
            metadata[record.name] = record
        return metadata

    def _load_metadata_with_env_fallbacks(self) -> dict[str, SecretMetadata]:
        metadata = self._load_metadata()
        for scope, secret_file in [
            ("core", self.settings.secrets_file),
            ("tool", self.settings.tool_secrets_file),
        ]:
            for name in load_secrets(secret_file):
                if name not in metadata:
                    metadata[name] = SecretMetadata(
                        name=name,
                        scope=scope,
                        exists=True,
                    )
        return metadata

    def _save_metadata(self, metadata: dict[str, SecretMetadata]) -> None:
        path = secret_metadata_path(self.settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "secrets": [
                record.to_dict()
                for record in sorted(metadata.values(), key=lambda item: item.name)
            ],
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def upsert_env_value(secrets_file: Path, key: str, value: str) -> None:
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if secrets_file.exists():
        lines = secrets_file.read_text(encoding="utf-8").splitlines()

    serialized = f"{key}={_serialize_env_value(value)}"
    updated = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        if not stripped or "=" not in stripped:
            continue
        candidate_key = stripped.split("=", 1)[0].strip()
        if candidate_key == key:
            lines[index] = serialized
            updated = True
            break

    if not updated:
        lines.append(serialized)

    secrets_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def remove_env_value(secrets_file: Path, key: str) -> bool:
    if not secrets_file.exists():
        return False
    lines = secrets_file.read_text(encoding="utf-8").splitlines()
    kept_lines: list[str] = []
    removed = False
    for line in lines:
        stripped = line.strip()
        normalized = stripped[7:].strip() if stripped.startswith("export ") else stripped
        if normalized and "=" in normalized and normalized.split("=", 1)[0].strip() == key:
            removed = True
            continue
        kept_lines.append(line)
    if removed:
        secrets_file.write_text("\n".join(kept_lines).rstrip() + "\n", encoding="utf-8")
    return removed


def _serialize_env_value(value: str) -> str:
    if not value or any(char.isspace() for char in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _utc_now() -> str:
    from time import gmtime, strftime

    return strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())
