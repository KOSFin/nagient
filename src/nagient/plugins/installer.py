from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from nagient.plugins.dependencies import (
    PluginDependencyError,
    install_plugin_dependencies,
    manifest_dependencies,
)


class PluginInstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class PluginInstallResult:
    plugin_id: str
    family: str
    version: str
    directory: Path
    source: str
    ref: str | None
    dependencies: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "family": self.family,
            "version": self.version,
            "directory": str(self.directory),
            "source": self.source,
            "ref": self.ref,
            "dependencies": self.dependencies,
        }


_FAMILY_MANIFESTS = {
    "transport": ("plugin.toml", "plugins_dir"),
    "provider": ("provider.toml", "providers_dir"),
    "tool": ("tool.toml", "tools_dir"),
}


def install_plugin(
    source: str,
    *,
    plugins_dir: Path,
    providers_dir: Path,
    tools_dir: Path,
    ref: str | None = None,
    force: bool = False,
    install_dependencies: bool = True,
    upgrade_dependencies: bool = False,
) -> PluginInstallResult:
    family_hint, repository, parsed_ref = _parse_source(source)
    ref = ref or parsed_ref
    if not _is_git_source(repository):
        raise PluginInstallError("Источник должен быть URL Git-репозитория.")

    with tempfile.TemporaryDirectory(prefix="nagient-plugin-") as temp_dir:
        checkout = Path(temp_dir) / "repo"
        command = ["git", "clone", "--depth", "1"]
        if ref:
            command.extend(["--branch", ref])
        command.extend([repository, str(checkout)])
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise PluginInstallError(f"Не удалось клонировать плагин: {detail}")

        manifest_path, family, manifest = _find_manifest(checkout, family_hint)
        plugin_id = _required_string(manifest, "id", manifest_path)
        version = _required_string(manifest, "version", manifest_path)
        try:
            dependencies, requirements_file = manifest_dependencies(manifest)
        except PluginDependencyError as exc:
            raise PluginInstallError(str(exc)) from exc
        destination_root = {
            "transport": plugins_dir,
            "provider": providers_dir,
            "tool": tools_dir,
        }[family]
        destination = destination_root / _safe_directory_name(plugin_id)
        if destination.exists():
            if not force:
                raise PluginInstallError(
                    f"Плагин {plugin_id!r} уже установлен в {destination}. "
                    "Используйте --force для замены."
                )
            shutil.rmtree(destination)
        destination_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            manifest_path.parent,
            destination,
            ignore=shutil.ignore_patterns(".git", ".github"),
        )
        if install_dependencies:
            try:
                dependency_status = install_plugin_dependencies(
                    destination,
                    dependencies,
                    requirements_file=requirements_file,
                    upgrade=upgrade_dependencies,
                )
            except PluginDependencyError as exc:
                shutil.rmtree(destination, ignore_errors=True)
                raise PluginInstallError(str(exc)) from exc
        else:
            dependency_status = {
                "status": "skipped",
                "dependencies": dependencies,
                "requirements_file": requirements_file,
            }
        metadata = {
            "plugin_id": plugin_id,
            "family": family,
            "version": version,
            "source": repository,
            "ref": ref,
            "installed_at": datetime.now(UTC).isoformat(),
            "dependencies": dependency_status,
        }
        (destination / ".nagient-plugin.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return PluginInstallResult(
            plugin_id=plugin_id,
            family=family,
            version=version,
            directory=destination,
            source=repository,
            ref=ref,
            dependencies=dependency_status,
        )


def list_installed_plugins(
    *,
    plugins_dir: Path,
    providers_dir: Path,
    tools_dir: Path,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    roots = {
        "transport": plugins_dir,
        "provider": providers_dir,
        "tool": tools_dir,
    }
    for family, root in roots.items():
        if not root.exists():
            continue
        for metadata_path in sorted(root.glob("*/.nagient-plugin.json")):
            try:
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                payload.setdefault("family", family)
                payload.setdefault("directory", str(metadata_path.parent))
                result.append(payload)
    return result


def remove_plugin(
    plugin_id: str,
    *,
    plugins_dir: Path,
    providers_dir: Path,
    tools_dir: Path,
) -> dict[str, object]:
    for root in (plugins_dir, providers_dir, tools_dir):
        candidate = root / _safe_directory_name(plugin_id)
        metadata_path = candidate / ".nagient-plugin.json"
        if candidate.is_dir() and metadata_path.exists():
            shutil.rmtree(candidate)
            return {"plugin_id": plugin_id, "removed": True, "directory": str(candidate)}
    raise PluginInstallError(f"Установленный плагин {plugin_id!r} не найден.")


def _parse_source(source: str) -> tuple[str | None, str, str | None]:
    family_hint: str | None = None
    repository = source.strip()
    if ":" in repository and repository.split(":", 1)[0] in _FAMILY_MANIFESTS:
        family_hint, repository = repository.split(":", 1)
    ref: str | None = None
    if "#" in repository:
        repository, ref = repository.rsplit("#", 1)
    return family_hint, repository, ref


def _is_git_source(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https", "ssh", "git", "file"} or source.startswith("git@")


def _find_manifest(
    checkout: Path,
    family_hint: str | None,
) -> tuple[Path, str, dict[str, object]]:
    candidates: list[tuple[Path, str]] = []
    families = [family_hint] if family_hint else list(_FAMILY_MANIFESTS)
    for family in families:
        if family is None:
            continue
        manifest_name, _ = _FAMILY_MANIFESTS[family]
        candidates.extend((path, family) for path in checkout.rglob(manifest_name))
    if len(candidates) != 1:
        names = ", ".join(str(path.relative_to(checkout)) for path, _ in candidates)
        raise PluginInstallError(
            "В репозитории должен быть ровно один манифест "
            f"plugin.toml/provider.toml/tool.toml; найдено: {names or 'ничего'}."
        )
    manifest_path, family = candidates[0]
    payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("type") != family:
        raise PluginInstallError(f"Манифест {manifest_path.name} имеет неверное поле type.")
    return manifest_path, family, payload


def _required_string(payload: dict[str, object], key: str, path: Path) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PluginInstallError(f"В {path.name} обязательно поле {key!r}.")
    return value.strip()


def _safe_directory_name(plugin_id: str) -> str:
    return plugin_id.replace("/", "_").replace("\\", "_").replace("..", "_")
