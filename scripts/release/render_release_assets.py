#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_TEMPLATES = {
    "scripts/install.sh": "install.sh",
    "scripts/update.sh": "update.sh",
    "scripts/uninstall.sh": "uninstall.sh",
    "scripts/install.ps1": "install.ps1",
    "scripts/update.ps1": "update.ps1",
    "scripts/uninstall.ps1": "uninstall.ps1",
    "docker/compose/docker-compose.yml": "docker-compose.yml",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render release assets from repository templates.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--update-base-url", required=True)
    parser.add_argument("--docker-image", required=True)
    parser.add_argument("--default-channel", required=True)
    parser.add_argument("--docker-project-name", required=True)
    parser.add_argument("--container-name", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    replacements = {
        "__NAGIENT_UPDATE_BASE_URL__": args.update_base_url.rstrip("/"),
        "__NAGIENT_DOCKER_IMAGE__": args.docker_image,
        "__NAGIENT_DEFAULT_CHANNEL__": args.default_channel,
        "__NAGIENT_DOCKER_PROJECT_NAME__": args.docker_project_name,
        "__NAGIENT_CONTAINER_NAME__": args.container_name,
    }

    for source_path, target_name in _TEMPLATES.items():
        template_path = REPO_ROOT / source_path
        rendered = template_path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            rendered = rendered.replace(old, new)

        target_path = output_dir / target_name
        target_path.write_text(rendered, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

