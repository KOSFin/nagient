from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path


class PluginDependencyError(RuntimeError):
    pass


def plugin_python(directory: Path) -> str:
    """Return the plugin interpreter when an isolated environment exists."""
    if os.name == "nt":
        candidate = directory / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = directory / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def install_plugin_dependencies(
    directory: Path,
    dependencies: list[str],
    *,
    requirements_file: str | None = None,
    upgrade: bool = False,
) -> dict[str, object]:
    requirements = [item.strip() for item in dependencies if item.strip()]
    requirements_path = directory / requirements_file if requirements_file else None
    if requirements_path is not None:
        try:
            requirements_path.resolve().relative_to(directory.resolve())
        except ValueError as exc:
            raise PluginDependencyError(
                "requirements_file должен находиться внутри каталога плагина."
            ) from exc
    if requirements_path is not None and not requirements_path.is_file():
        raise PluginDependencyError(
            f"Файл зависимостей {requirements_file!r} не найден в плагине."
        )
    if not requirements and requirements_path is None:
        return {"status": "not_required", "dependencies": []}

    environment = directory / ".venv"
    if not environment.exists():
        venv.EnvBuilder(with_pip=True, clear=False).create(environment)

    command = [plugin_python(directory), "-m", "pip", "install"]
    if upgrade:
        command.append("--upgrade")
    if requirements_path is not None:
        command.extend(["-r", str(requirements_path)])
    command.extend(requirements)
    completed = subprocess.run(
        command,
        cwd=directory,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise PluginDependencyError(
            f"Не удалось установить зависимости плагина: {detail}"
        )
    return {
        "status": "installed",
        "dependencies": requirements,
        "requirements_file": requirements_file,
        "python": plugin_python(directory),
    }


def activate_plugin_dependencies(directory: Path) -> None:
    """Make an installed plugin venv importable by its dynamically loaded module."""
    python = Path(plugin_python(directory))
    if python == Path(sys.executable):
        return
    if os.name == "nt":
        site_packages = python.parent.parent / "Lib" / "site-packages"
    else:
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages = python.parent.parent / "lib" / version / "site-packages"
    if site_packages.is_dir() and str(site_packages) not in sys.path:
        sys.path.insert(0, str(site_packages))


def manifest_dependencies(payload: dict[str, object]) -> tuple[list[str], str | None]:
    raw_dependencies = payload.get("dependencies", [])
    if not isinstance(raw_dependencies, list) or not all(
        isinstance(item, str) and item.strip() for item in raw_dependencies
    ):
        raise PluginDependencyError("Поле dependencies должно быть списком строк.")
    requirements_file = payload.get("requirements_file")
    if requirements_file is not None and (
        not isinstance(requirements_file, str) or not requirements_file.strip()
    ):
        raise PluginDependencyError("Поле requirements_file должно быть строкой.")
    return [item.strip() for item in raw_dependencies], requirements_file
